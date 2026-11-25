@echo off
chcp 65001 >nul
title Controllo singolo - Monitor Arena
cd /d "%~dp0"
python monitor_arena.py check
echo.
pause
