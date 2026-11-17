@echo off
rem Liga o PostgreSQL em um container Docker (precisa do Docker Desktop instalado e aberto).
cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
  echo.
  echo  O Docker nao foi encontrado. Voce tem duas opcoes:
  echo    1. Instalar o Docker Desktop: https://www.docker.com/products/docker-desktop/
  echo    2. Instalar o PostgreSQL direto no Windows - veja o README, secao "PostgreSQL".
  echo.
  pause
  exit /b 1
)

docker compose up -d
if errorlevel 1 (
  echo.
  echo  Nao consegui ligar o banco. O Docker Desktop esta aberto?
  pause
  exit /b 1
)
echo.
echo  PostgreSQL ligado. Agora e so abrir o iniciar.bat.
pause
