# Receita Segura

Plataforma de receitas médicas assinadas digitalmente — projeto acadêmico (UNAMA).

- **Framework back-end:** FastAPI + Python
- **Front-end:** nenhum framework — PWA com HTML, CSS e JavaScript puro
- **Banco:** SQLite (arquivo em `data/`, criado automaticamente)

## Como rodar (Windows)

Dê dois cliques em **`iniciar.bat`** (na primeira vez ele cria o ambiente e instala as dependências).

Ou, pelo terminal:

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn backend.main:app --reload
```

- Site: http://localhost:8000
- Documentação interativa das APIs (Swagger): http://localhost:8000/docs

| Perfil   | E-mail             | Senha   |
|----------|--------------------|---------|
| Médico   | camila@clinica.com | demo123 |
| Paciente | joao@email.com     | demo123 |

Para voltar ao estado inicial, pare o servidor e apague a pasta `data/`.

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

## Estrutura

```
index.html, css/, js/, assets/    → front-end
manifest.webmanifest              → PWA (instalar como app)
service-worker.js                 → PWA (cache / funcionamento offline)
backend/main.py                   → cria o app FastAPI e junta as 13 APIs
backend/database.py               → SQLite e criação das tabelas
backend/seguranca.py              → scrypt, SHA-256, assinatura Ed25519
backend/dependencias.py           → usuário logado, permissões, auditoria
backend/receitas_servico.py       → regras de emissão e verificação
backend/seed.py                   → dados de demonstração e catálogo
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
| 13 | Status                  | `routers/status.py`             | `GET /api/status`, `GET /api/status/receitas/{codigo}`, `POST /api/status/receitas/{codigo}/cancelar` |
