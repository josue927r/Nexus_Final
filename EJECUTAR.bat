@echo off
cd /d "%~dp0"

IF NOT EXIST "venv\Scripts\python.exe" (
    echo Creando entorno virtual...
    python -m venv venv
    echo Instalando dependencias...
    .\venv\Scripts\pip install -r requirements.txt
)

.\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
