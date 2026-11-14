# Corregir el giro de PDF para Illustrator

Herramienta independiente de la correccion de simbolos. Integra la rotacion
`/Rotate` dentro del contenido y ajusta las dimensiones de la pagina, conservando
los vectores. No convierte el texto ni corrige fuentes.

## Instalacion y uso

Requiere Windows y Python 3 con Tkinter. Desde esta carpeta:

```powershell
python -m pip install -r requirements.txt
python arreglar_pdf.py
```

Tambien puedes abrir `Arreglar PDF.bat`, arrastrar PDF sobre el lanzador o usar
el boton de seleccion de la ventana. `tkinterdnd2` permite arrastrarlos dentro
de la ventana; sin ese paquete puedes usar el boton.

Por defecto genera `nombre-FIXED.pdf` junto al original. La opcion
**Reemplazar el original** sobrescribe el PDF seleccionado. Si no hay paginas
giradas, no crea una copia. Si el nombre ya termina en `-FIXED`, reutiliza esa
ruta en lugar de crear `-FIXED-FIXED`.

## Dos problemas distintos

- **Orientacion incorrecta:** usa esta carpeta.
- **Simbolos rotos o fuentes:** usa [simbolos-y-fuentes/](../simbolos-y-fuentes/README.md).
- **Ambos problemas:** corrige primero el giro y procesa despues el archivo
  `-FIXED.pdf` con la herramienta de simbolos.

No necesitas instalar el menu contextual de la herramienta de simbolos para
usar esta aplicacion.
