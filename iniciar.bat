@echo off
rem Inicia o Receita Segura (FastAPI). Na primeira vez, cria o ambiente e instala as dependencias.
rem O banco PostgreSQL precisa estar ligado antes (veja iniciar-banco.bat e o README).
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual Python...
  python -m venv .venv || py -m venv .venv
)
echo Verificando dependencias...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt

rem Endereco do banco: postgresql://USUARIO:SENHA@SERVIDOR:PORTA/NOME_DO_BANCO
rem Se voce ja definiu DATABASE_URL no Windows, ela e respeitada; senao usamos a do docker-compose.yml.
if "%DATABASE_URL%"=="" set DATABASE_URL=postgresql://receita:receita@localhost:5432/receita_segura

echo.
echo  Site:           http://localhost:8000
echo  Documentacao:   http://localhost:8000/docs
echo.
".venv\Scripts\python.exe" -m uvicorn backend.main:app --reload --port 8000
