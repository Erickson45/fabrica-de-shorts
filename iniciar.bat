@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo A Fabrica ainda nao foi instalada. Rode o instalar.bat primeiro.
  pause
  exit /b 1
)
echo Abrindo o painel em http://localhost:5050 ...
start "" http://localhost:5050
".venv\Scripts\python.exe" painel.py
pause
