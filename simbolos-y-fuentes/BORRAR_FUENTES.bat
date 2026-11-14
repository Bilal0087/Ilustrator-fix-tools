@echo off
chcp 65001 >nul
title Borrar las fuentes instaladas por ArreglarPDF
echo Quitando las fuentes que instalo "Arreglar y abrir en Illustrator"
echo y borrando lo descargado para recuperar espacio...
echo.
py "%~dp0fuentes.py" --borrar
echo.
pause
