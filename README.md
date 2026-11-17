# Receita Segura

Plataforma de receitas médicas assinadas digitalmente — projeto acadêmico (UNAMA).

- **Framework back-end:** FastAPI + Python
- **Front-end:** nenhum framework — PWA com HTML, CSS e JavaScript puro
- **Banco:** PostgreSQL (veja a seção [PostgreSQL](#postgresql) abaixo)

## Como rodar (Windows)

1. **Ligue o banco PostgreSQL** (só uma vez; depois ele já fica ligado): dê dois cliques em **`iniciar-banco.bat`**
   (precisa do Docker Desktop) ou instale o PostgreSQL direto no Windows — as duas opções estão na seção
   [PostgreSQL](#postgresql).
2. Dê dois cliques em **`iniciar.bat`** (na primeira vez ele cria o ambiente e instala as dependências).

Ou, pelo terminal:

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
set DATABASE_URL=postgresql://receita:receita@localhost:5432/receita_segura
.venv\Scripts\python -m uvicorn backend.main:app --reload
```

- Site: http://localhost:8000
- Documentação interativa das APIs (Swagger): http://localhost:8000/docs

| Perfil   | E-mail             | Senha   |
|----------|--------------------|---------|
| Médico   | camila@clinica.com | demo123 |
| Paciente | joao@email.com     | demo123 |

Para voltar ao estado inicial, veja "Zerar o banco" na seção [PostgreSQL](#postgresql).

### Como rodar no celular

Para acessar o sistema pelo celular através da rede local:

1. **Conecte o computador e o celular à mesma rede Wi-Fi.**

2. **Inicie o servidor no computador:**

   ```powershell
   .venv\Scripts\python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

Descubra o endereço IP do computador:

ipconfig

Procure pelo endereço IPv4 da conexão utilizada pelo computador.

Exemplo:

IPv4: 192.168.0.79

Abra o navegador no celular e acesse:

http://192.168.0.79:8000

Substitua 192.168.0.79 pelo IPv4 do seu computador.

Mantenha o terminal aberto enquanto estiver utilizando o sistema pelo celular.

Importante: o computador e o celular precisam estar conectados à mesma rede para que o acesso funcione.

## PostgreSQL

### O que mudou em relação ao SQLite

O SQLite guardava tudo num **arquivo** (`data/receita-segura.db`). O PostgreSQL é um **programa servidor** que
fica rodando no computador (ou em outra máquina) e o sistema conversa com ele pela rede, na porta `5432`.
Por isso existem duas coisas novas: o servidor precisa estar **ligado** antes de abrir o sistema, e o sistema
precisa saber o **endereço** dele.

Esse endereço é a variável `DATABASE_URL`, no formato:

```
postgresql://USUARIO:SENHA@SERVIDOR:PORTA/NOME_DO_BANCO
postgresql://receita:receita@localhost:5432/receita_segura      <- o padrão usado aqui
```

O `iniciar.bat` já usa esse padrão se você não definir nada. Se o servidor estiver desligado, o sistema avisa
com uma mensagem clara ao iniciar.

### Opção A — Docker (mais simples)

1. Instale o [Docker Desktop](https://www.docker.com/products/docker-desktop/) e deixe-o aberto.
2. Dê dois cliques em **`iniciar-banco.bat`** (ou rode `docker compose up -d` na pasta do projeto).
3. Pronto: o banco `receita_segura` já existe, com o usuário `receita` e a senha `receita`.

Os dados ficam num volume do Docker, então não se perdem ao desligar o computador.
Para desligar o banco: `docker compose stop`. Para ligar de novo: `docker compose start`.

### Opção B — Instalar o PostgreSQL direto no Windows

1. Baixe o instalador em https://www.postgresql.org/download/windows/ e instale com as opções padrão.
   Durante a instalação ele pede uma **senha para o usuário `postgres`** (o administrador) — anote-a.
2. No menu Iniciar, abra **SQL Shell (psql)**, aperte Enter nas perguntas (servidor, banco, porta, usuário)
   e digite a senha do `postgres`.
3. Cole estes dois comandos (um de cada vez):

   ```sql
   CREATE USER receita WITH PASSWORD 'receita';
   CREATE DATABASE receita_segura OWNER receita;
   ```

4. Abra o `iniciar.bat`. As tabelas são criadas sozinhas na primeira vez.

### Trazer os dados do SQLite antigo

Se você já tinha receitas no `data/receita-segura.db`, copie-as para o PostgreSQL **uma vez** (com o banco ligado):

```bash
.venv\Scripts\python -m backend.migrar_sqlite --limpar
```

O script mantém ids, assinaturas e datas exatamente como estavam, então receitas antigas continuam
verificáveis. O arquivo `.db` não é alterado — guarde-o como backup. (`--limpar` apaga o que já estiver no
PostgreSQL, por exemplo os dados de demonstração criados se você abriu o sistema antes de migrar.)

### Zerar o banco (voltar ao estado inicial)

```bash
docker compose down -v
docker compose up -d
```

(Sem Docker: no **SQL Shell (psql)** rode `DROP DATABASE receita_segura;` e `CREATE DATABASE receita_segura OWNER receita;`.)

### Olhar os dados e fazer backup

- Para **ver as tabelas** com interface gráfica, instale o [DBeaver](https://dbeaver.io/) ou o pgAdmin (já vem
  com o instalador do Windows) e conecte com os mesmos dados do `DATABASE_URL`.
- **Backup:** `pg_dump -U receita receita_segura > backup.sql` (com Docker:
  `docker exec receita-segura-db pg_dump -U receita receita_segura > backup.sql`).

### Antes de colocar em produção

A senha `receita` é só para testes. Em produção: senha forte, `DATABASE_URL` definida no servidor (nunca no
código), banco fora da internet pública e backups automáticos.

## Documentos médicos (além da receita)

No painel do médico, o card **Emitir documento** tem abas:

- **Encaminhamento (guia de referência):** dados do paciente, especialidade de destino e prioridade, motivo da avaliação solicitada, resumo da história clínica/condutas já realizadas e, opcionalmente, hipótese diagnóstica + CID-10/CID-11.
- **Relatório / laudo:** histórico e avaliação, diagnóstico (CID opcional), limitações associadas e recomendações de adaptação (sala individual, tempo extra de prova etc.).
- **Atestado simples:** afastamento por N dias (com o número por extenso) ou comparecimento a atendimento.

Todos são assinados (SHA-256 + Ed25519, igual às receitas), saem em PDF com carimbo do médico, assinatura digital e QR Code, e podem ser conferidos publicamente em `/?verificar=CODIGO` (a verificação não mostra paciente nem conteúdo clínico). Códigos: `EN-`, `LM-` e `AT-`. O médico pode cancelar um documento (a assinatura continua válida, mas ele passa a constar como cancelado).

**Sigilo:** hipótese diagnóstica e CID só são aceitos se o médico marcar que o paciente autorizou expressamente — o servidor recusa o documento caso contrário, e a autorização fica registrada dentro do conteúdo assinado.

Na primeira inicialização, 3 documentos de exemplo são criados para o paciente de demonstração.

## Estrutura

```
index.html, css/, js/, assets/    → front-end
manifest.webmanifest              → PWA (instalar como app)
service-worker.js                 → PWA (cache / funcionamento offline)
backend/main.py                   → cria o app FastAPI e junta as 14 APIs
backend/database.py               → conexão com o PostgreSQL e criação das tabelas
backend/migrar_sqlite.py          → copia os dados do SQLite antigo para o PostgreSQL
backend/seguranca.py              → scrypt, SHA-256, assinatura Ed25519
backend/dependencias.py           → usuário logado, permissões, auditoria
backend/receitas_servico.py       → regras de emissão e verificação
backend/seed.py                   → dados de demonstração e catálogo
backend/documentos_servico.py     → regras dos documentos (encaminhamento, laudo, atestado)
backend/pdf_documentos.py         → PDF dos documentos (carimbo, assinatura, QR Code)
backend/validacao.py              → CPF, telefone, datas, CID-10/CID-11
backend/routers/                  → uma API por arquivo (lista abaixo)
```

## APIs internas

| #  | API                     | Arquivo                         | Rotas principais |
|----|-------------------------|---------------------------------|------------------|
| 1  | Autenticação            | `routers/autenticacao.py`       | `POST /api/auth/login`, `POST /api/auth/ativar`, `GET /api/auth/eu`, `POST /api/auth/logout` |
| 2  | Usuários                | `routers/usuarios.py`           | `POST /api/usuarios/medicos`, `GET/PUT /api/usuarios/eu`, `PUT /api/usuarios/eu/senha` |
| 3  | Pacientes               | `routers/pacientes.py`          | `GET/POST /api/pacientes`, `GET /api/pacientes/{id}` |
| 4  | Receitas                | `routers/receitas.py`           | `GET/POST /api/receitas`, `GET /api/receitas/{codigo}` |
| 5  | Medicamentos            | `routers/medicamentos.py`       | `GET /api/medicamentos?busca=`, `GET /api/medicamentos/{id}` |
| 6  | Assinatura/Integridade  | `routers/assinatura.py`         | `GET /api/assinatura/chaves/{medico}`, `GET /api/assinatura/receitas/{codigo}`, `GET /api/assinatura/integridade`, `POST /api/assinatura/conferir` |
| 7  | Verificação             | `routers/verificacao.py`        | `GET /api/verificar/{codigo}` (pública) |
| 8  | QR Code                 | `routers/qrcode_api.py`         | `GET /api/qrcode/{codigo}.png` |
| 9  | PDF                     | `routers/pdf.py`                | `GET /api/pdf/{codigo}` |
| 10 | Compartilhamento        | `routers/compartilhamento.py`   | `POST/GET /api/compartilhamentos`, `DELETE /api/compartilhamentos/{id}`, `GET /api/compartilhamentos/acesso/{token}` (+ `/pdf`, `/dispensar`) |
| 11 | Histórico               | `routers/historico.py`          | `GET /api/historico`, `GET /api/historico/pacientes/{id}` |
| 12 | Auditoria               | `routers/auditoria.py`          | `GET /api/auditoria` |
| 14 | Documentos              | `routers/documentos.py`         | `POST /api/documentos/encaminhamentos`, `/relatorios`, `/atestados`; `GET /api/documentos`, `GET /api/documentos/{codigo}` (+ `/pdf`), `POST /api/documentos/{codigo}/cancelar` |
| 13 | Status                  | `routers/status.py`             | `GET /api/status`, `GET /api/status/receitas/{codigo}`, `POST /api/status/receitas/{codigo}/cancelar` |
