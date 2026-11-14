@echo off
chcp 65001 >nul
rem Arrastra uno o varios PDF para hacer una copia en CURVAS (ultimo recurso).
rem Lo normal es NO usar esto: mejor clic derecho sobre el PDF > "Arreglar y abrir
rem en Illustrator", que instala las fuentes y deja el texto EDITABLE.
python "%~dp0vectorizar_pdf.py" %*
echo.
echo ------------------------------------------------------------
echo Hecho. Se creo un PDF  "_curvas.pdf"  junto a cada PDF (texto en curvas).
pause
