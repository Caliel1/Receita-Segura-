"""Copia os dados de um banco SQLite antigo (data/receita-segura.db) para o PostgreSQL.

Uso (com o PostgreSQL ligado e DATABASE_URL configurada):

    python -m backend.migrar_sqlite                       # usa data/receita-segura.db
    python -m backend.migrar_sqlite caminho/do/banco.db   # outro arquivo
    python -m backend.migrar_sqlite --limpar              # apaga o que já existe no PostgreSQL antes

Os ids, as assinaturas e as datas são copiados exatamente como estão, então receitas e documentos já
emitidos continuam verificáveis. O arquivo SQLite não é alterado (é aberto só para leitura).
"""
import argparse
import sqlite3
import sys

import psycopg

from .database import DATABASE_URL, RAIZ, _url_sem_senha, criar_tabelas

# Ordem importa: quem tem chave estrangeira vem depois da tabela que ele referencia.
TABELAS = ["usuarios", "sessoes", "medico_pacientes", "medicamentos", "receitas", "documentos",
           "compartilhamentos", "auditoria"]
COM_ID = {"usuarios", "medicamentos", "receitas", "documentos", "compartilhamentos", "auditoria"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sqlite", nargs="?", default=str(RAIZ / "data" / "receita-segura.db"),
                    help="arquivo SQLite de origem")
    ap.add_argument("--limpar", action="store_true", help="apaga os dados atuais do PostgreSQL antes de copiar")
    args = ap.parse_args()

    origem = sqlite3.connect(f"file:{args.sqlite}?mode=ro", uri=True)  # somente leitura
    origem.row_factory = sqlite3.Row
    tabelas_origem = {l[0] for l in origem.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "usuarios" not in tabelas_origem:
        print(f"'{args.sqlite}' não parece ser um banco do Receita Segura.")
        return 1

    print(f"Origem:  {args.sqlite}\nDestino: {_url_sem_senha()}")
    criar_tabelas()  # garante que as tabelas existem no PostgreSQL

    with psycopg.connect(DATABASE_URL) as destino:  # uma transação só: ou copia tudo, ou nada
        existentes = {t: destino.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABELAS}
        if any(existentes.values()):
            if not args.limpar:
                print("\nO PostgreSQL já tem dados:", {t: n for t, n in existentes.items() if n})
                print("Rode de novo com --limpar para apagá-los e copiar o SQLite no lugar.")
                return 1
            destino.execute("TRUNCATE " + ", ".join(TABELAS) + " RESTART IDENTITY CASCADE")

        for tabela in TABELAS:
            if tabela not in tabelas_origem:
                print(f"  {tabela:<18} (não existe no SQLite — ignorada)")
                continue
            colunas_origem = [c["name"] for c in origem.execute(f"PRAGMA table_info({tabela})")]
            colunas_destino = {r[0] for r in destino.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s", (tabela,))}
            colunas = [c for c in colunas_origem if c in colunas_destino]  # só as que existem nos dois
            linhas = [tuple(l[c] for c in colunas) for l in origem.execute(f"SELECT {', '.join(colunas)} FROM {tabela}")]
            if linhas:
                with destino.cursor() as cur:
                    cur.executemany(
                        f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({', '.join(['%s'] * len(colunas))})", linhas)
            print(f"  {tabela:<18} {len(linhas):>5} linha(s)")

        # Como copiamos os ids na mão, o contador automático precisa continuar do maior id existente.
        for tabela in COM_ID:
            destino.execute(
                f"SELECT setval(pg_get_serial_sequence('{tabela}', 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {tabela}")
    print("\nMigração concluída. Inicie o servidor normalmente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
