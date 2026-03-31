@echo off
title Content Generation Pipeline - Startup
chcp 65001 >nul
color 0A

echo ============================================================
echo   Agent-based Content Generation Pipeline
echo   Starting all services...
echo ============================================================
echo.

:: ─── Kiểm tra thư mục hiện tại ───────────────────────────────
cd /d "%~dp0"

:: ─── Kiểm tra virtual environment ───────────────────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found at .venv\
    echo Please run: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements\development.txt
    pause
    exit /b 1
)

:: ─── Kiểm tra file .env ──────────────────────────────────────
if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Please copy .env.example to .env and fill in your API keys.
    pause
    exit /b 1
)

echo [1/4] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [2/4] Running database migrations...
python manage.py migrate --settings=config.settings.development
if errorlevel 1 (
    echo [ERROR] Migration failed. Check your DATABASE_URL in .env
    pause
    exit /b 1
)

echo.
echo [3/4] Starting Celery worker...
start "Celery Worker" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate.bat && celery -A config worker -l info -P solo"

echo Waiting for Celery to initialize...
timeout /t 3 /nobreak >nul

echo.
echo [4/4] Starting Daphne ASGI server...
start "Daphne Server" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate.bat && daphne -b 127.0.0.1 -p 8000 config.asgi:application"

echo.
echo ============================================================
echo   All services started!
echo.
echo   Dashboard  : http://127.0.0.1:8000/
echo   Admin      : http://127.0.0.1:8000/admin/
echo.
echo   [Celery Worker]  - separate window
echo   [Daphne Server]  - separate window
echo.
echo   Press any key to open the dashboard in your browser...
echo ============================================================
pause >nul

start http://127.0.0.1:8000/
