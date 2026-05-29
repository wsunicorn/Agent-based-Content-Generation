@echo off
title Content Generation Pipeline - Startup
chcp 65001 >nul
color 0A

echo ============================================================
echo   Agent-based Content Generation Pipeline
echo   Starting all services...
echo ============================================================
echo.

:: --- Check current directory ---
cd /d "%~dp0"

:: --- Check virtual environment ---
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found at .venv\
    echo Please run: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements\development.txt
    pause
    exit /b 1
)

:: --- Check .env file ---
if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Please copy .env.example to .env and fill in your API keys.
    pause
    exit /b 1
)

echo [1/5] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [2/5] Running database migrations...
python manage.py migrate --settings=config.settings.development
if errorlevel 1 (
    echo [ERROR] Migration failed. Check your DATABASE_URL in .env
    pause
    exit /b 1
)

echo.
echo [3/5] Starting Celery Worker 1 (solo pool)...
start "Celery Worker 1" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate.bat && set DJANGO_SETTINGS_MODULE=config.settings.development&& celery -A config worker -l info -P solo -n worker1@%%h"

echo [4/5] Starting Celery Worker 2 (solo pool)...
start "Celery Worker 2" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate.bat && set DJANGO_SETTINGS_MODULE=config.settings.development&& celery -A config worker -l info -P solo -n worker2@%%h"

echo Waiting for Celery workers to initialize...
timeout /t 4 /nobreak >nul

echo.
echo [5/5] Starting Daphne ASGI server...
start "Daphne Server" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate.bat && set DJANGO_SETTINGS_MODULE=config.settings.development&& daphne -b 127.0.0.1 -p 8000 config.asgi:application"

echo.
echo ============================================================
echo   All services started!
echo.
echo   Dashboard  : http://127.0.0.1:8000/
echo   Admin      : http://127.0.0.1:8000/admin/
echo.
echo   [Celery Worker 1]  - separate window (solo pool)
echo   [Celery Worker 2]  - separate window (solo pool)
echo   [Daphne Server]    - separate window
echo.
echo   Press any key to open the dashboard in your browser...
echo ============================================================
pause >nul

start http://127.0.0.1:8000/
