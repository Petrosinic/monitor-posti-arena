@echo off
chcp 65001 >nul
title Monitor posti Arena di Verona - NON CHIUDERE
cd /d "%~dp0"
:loop
echo.
echo ===== avvio monitor: %date% %time% =====
python monitor_arena.py watch
echo.
echo Il monitor si e fermato. Riparto fra 60 secondi. Premi CTRL+C per uscire.
timeout /t 60 /nobreak >nul
goto loop
