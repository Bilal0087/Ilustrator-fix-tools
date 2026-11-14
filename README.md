# Arreglar PDF para Illustrator

Este repositorio contiene **dos herramientas independientes**:

| Problema | Herramienta | Ubicacion |
| --- | --- | --- |
| Simbolos que se convierten en cuadros o fuentes incorrectas | Arreglar y abrir en Illustrator | Raiz del repositorio; instrucciones debajo |
| PDF que Illustrator abre girado | Corregir giro del PDF | [giro-pdf/](giro-pdf/README.md) |

Si necesitas ambas, corrige primero el giro y pasa el PDF `-FIXED.pdf` a la
herramienta de simbolos. Cada herramienta tiene sus propias dependencias.

## Simbolos y fuentes

Herramienta para Windows: conserva como texto editable las fuentes de texto
instaladas (incluidas Arial/Calibri en PDF Type0/CID) o que puede proporcionar.
Convierte a curvas las fuentes matematicas y de simbolos, y los operadores,
letras griegas y caracteres privados/sin Unicode dentro de fuentes de texto.
Las fuentes desconocidas que no puede proporcionar siguen pasando a curvas.

## Uso

```powershell
python -m pip install -r requirements.txt
python fuentes.py --dry "C:\ruta\original.pdf"
python arreglar_y_abrir.py "C:\ruta\original.pdf" --no-open
```

Abre `original_para_illustrator.pdf` en Illustrator. Usa siempre el PDF original:
un documento ya convertido a curvas no conserva texto recuperable. Si el propio
original ya dibuja cuadros en lugar de simbolos, vectorizar no los reconstruye.
El diagnostico `--dry` enumera decisiones por fuente; la seleccion adicional de
simbolos por caracter se realiza durante la conversion.

`INSTALAR.bat` configura el menu contextual. Cierra y vuelve a abrir Illustrator
si se han instalado fuentes nuevas. `--editable` sigue aceptandose por
compatibilidad; el texto instalado ya se conserva por defecto.

**`Vectorizar PDF (arrastra aqui).bat` y `--vector` convierten todo a curvas**:
son el modo de conversion completa, no el flujo hibrido.

## Verificacion

```powershell
python -m unittest -v test_hibrido
python -m compileall -q arreglar_y_abrir.py fuentes.py vectorizar_pdf.py diagnostico_fuentes.py test_hibrido.py
```

Las pruebas generan un PDF con prosa, simbolos e imagen transparente y comprueban
texto extraible, posiciones y renderizado. No sustituyen la comprobacion del PDF
real en Illustrator. No hay compilacion adicional ni servidor web.

PyMuPDF se fija en 1.28.2: con 2.0 se reprodujo desplazamiento del texto restante
al eliminar simbolos intercalados. Antes de actualizar, ejecuta las regresiones.
El modo selectivo corrige tambien paginas giradas, conservando su orientacion,
recorte, enlaces internos y metadatos. El modo completo reutiliza el aislamiento
del texto para conservar imagenes y graficos originales.

Si falla una pagina, se interrumpe la conversion sin sustituir la salida anterior.
La escritura se realiza primero en un archivo temporal; nunca se permite usar el
original como ruta de salida. `--dry` tampoco crea carpetas.
