@echo off
rem Inicia o Receita Segura (FastAPI). Na primeira vez, cria o ambiente e instala as dependencias.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual Python...
  python -m venv .venv || py -m venv .venv
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo.
echo  Site:           http://localhost:8000
echo  Documentacao:   http://localhost:8000/docs
echo.
".venv\Scripts\python.exe" -m uvicorn backend.main:app --reload --port 8000
