@echo off
rem Abre la herramienta de giro con el Python instalado en este equipo.
where pyw >nul 2>nul
if not errorlevel 1 (
    start "" pyw -3 "%~dp0arreglar_pdf.py" %*
    exit /b
)
where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw "%~dp0arreglar_pdf.py" %*
    exit /b
)
echo No se encontro Python. Instala Python 3 y las dependencias de requirements.txt.
pause
