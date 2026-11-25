@echo off
chcp 65001 >nul
title Configura Telegram - Monitor Arena
mode con: cols=78 lines=50
cd /d "%~dp0"
python monitor_arena.py setup
echo.
pause
