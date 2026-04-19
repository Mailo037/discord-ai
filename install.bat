@echo off
title Discord AI Bot - Setup & Run
echo ==========================================
echo Checke/Installiere Abhängigkeiten...
echo (Das kann beim ersten Mal kurz dauern)
echo ==========================================

python -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [FEHLER] Etwas ist bei der Installation schiefgelaufen. 🥀
    pause
    exit /b %errorlevel%
)

echo.
echo [INFO] Alle Abhängigkeiten sind bereit! ✅
echo [INFO] Starte den Bot jetzt...
echo ==========================================
echo.

python bot.py

echo.
echo [INFO] Bot wurde beendet.
pause