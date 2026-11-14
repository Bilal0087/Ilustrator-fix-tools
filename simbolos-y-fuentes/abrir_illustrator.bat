@echo off
chcp 65001 >nul
title Arreglar PDF para Illustrator
py "%~dp0arreglar_y_abrir.py" %*
