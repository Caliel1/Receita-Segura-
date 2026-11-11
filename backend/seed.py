"""Dados de demonstração — as mesmas contas que o front-end mostrava."""
from .database import conectar
from .receitas_servico import emitir_receita
from .seguranca import gerar_codigo_convite, gerar_hash_senha, gerar_par_de_chaves

# (nome, classe, posologia sugerida, controlado)
MEDICAMENTOS = [
    ("Amoxicilina 500mg", "Antibiótico", "1 cápsula de 8 em 8h, por 7 dias", 0),
    ("Azitromicina 500mg", "Antibiótico", "1 comprimido ao dia, por 3 dias", 0),
    ("Cefalexina 500mg", "Antibiótico", "1 cápsula de 6 em 6h, por 7 dias", 0),
    ("Dipirona 1g", "Analgésico", "1 comprimido se dor, até de 6 em 6h", 0),
    ("Paracetamol 750mg", "Analgésico", "1 comprimido de 6 em 6h, se dor ou febre", 0),
    ("Ibuprofeno 600mg", "Anti-inflamatório", "1 comprimido de 8 em 8h, após as refeições, por 5 dias", 0),
    ("Nimesulida 100mg", "Anti-inflamatório", "1 comprimido de 12 em 12h, por 5 dias", 0),
    ("Prednisona 20mg", "Corticoide", "1 comprimido pela manhã, por 5 dias", 0),
    ("Loratadina 10mg", "Antialérgico", "1 comprimido ao dia", 0),
    ("Omeprazol 20mg", "Protetor gástrico", "1 cápsula em jejum, pela manhã", 0),
    ("Ondansetrona 8mg", "Antiemético", "1 comprimido de 8 em 8h, se enjoo", 0),
    ("Losartana 50mg", "Anti-hipertensivo", "1 comprimido ao dia", 0),
    ("Hidroclorotiazida 25mg", "Diurético", "1 comprimido pela manhã", 0),
    ("Anlodipino 5mg", "Anti-hipertensivo", "1 comprimido ao dia", 0),
    ("Metformina 850mg", "Antidiabético", "1 comprimido após o almoço e o jantar", 0),
    ("Sinvastatina 20mg", "Hipolipemiante", "1 comprimido à noite", 0),
    ("Levotiroxina 50mcg", "Hormônio tireoidiano", "1 comprimido em jejum, 30 min antes do café", 0),
    ("Salbutamol 100mcg spray", "Broncodilatador", "2 jatos se falta de ar, até de 4 em 4h", 0),
    ("Sulfato ferroso 40mg", "Suplemento", "1 comprimido ao dia, longe das refeições", 0),
    ("Vitamina D 7.000 UI", "Suplemento", "1 cápsula por semana", 0),
    ("Sertralina 50mg", "Antidepressivo", "1 comprimido pela manhã", 1),
    ("Fluoxetina 20mg", "Antidepressivo", "1 cápsula pela manhã", 1),
    ("Clonazepam 2mg", "Ansiolítico", "1 comprimido à noite", 1),
    ("Amitriptilina 25mg", "Antidepressivo", "1 comprimido à noite", 1),
    ("Tramadol 50mg", "Analgésico opioide", "1 cápsula de 8 em 8h, se dor intensa", 1),
]


def popular_se_vazio() -> None:
    db = conectar()
    try:
        if db.execute("SELECT COUNT(*) FROM medicamentos").fetchone()[0] == 0:
            db.executemany(
                "INSERT INTO medicamentos (nome, classe, posologia_sugerida, controlado) VALUES (?, ?, ?, ?)",
                MEDICAMENTOS,
            )

        if db.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] > 0:
            return

        publica, privada = gerar_par_de_chaves()
        medico_id = db.execute(
            """INSERT INTO usuarios (papel, nome, email, senha_hash, crm, especialidade, chave_publica, chave_privada)
               VALUES ('medico', ?, ?, ?, ?, ?, ?, ?)""",
            ("Dra. Camila Duarte", "camila@clinica.com", gerar_hash_senha("demo123"), "12345-AM", "Clínica Geral",
             publica, privada),
        ).lastrowid

        pacientes = [
            ("João Ferreira Lima", "joao@email.com", gerar_hash_senha("demo123"), "2026-09-02"),
            ("Beatriz Souza Nunes", None, None, "2026-08-28"),
            ("Renato Alves Costa", None, None, "2026-08-15"),
        ]
        ids = []
        for nome, email, senha, atendimento in pacientes:
            convite = None if senha else gerar_codigo_convite()
            pid = db.execute(
                "INSERT INTO usuarios (papel, nome, email, senha_hash, codigo_convite) VALUES ('paciente', ?, ?, ?, ?)",
                (nome, email, senha, convite),
            ).lastrowid
            db.execute("INSERT INTO medico_pacientes (medico_id, paciente_id, ultimo_atendimento) VALUES (?, ?, ?)",
                       (medico_id, pid, atendimento))
            ids.append(pid)

        emitir_receita(
            db, medico_id, ids[0],
            [{"nome": "Amoxicilina 500mg", "posologia": "de 8 em 8h, por 7 dias"},
             {"nome": "Dipirona 1g", "posologia": "se dor, até de 6 em 6h"}],
            "Repouso relativo por 3 dias.",
            emitida_em="2026-08-14T13:41:00.000Z",
        )
        print("Banco criado com dados de demonstração.")
    finally:
        db.close()
