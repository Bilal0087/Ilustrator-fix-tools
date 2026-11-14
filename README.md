# Herramientas PDF para Illustrator

Dos herramientas independientes, cada una con su codigo, lanzadores y dependencias:

| Carpeta | Para que sirve | Como abrirla |
| --- | --- | --- |
| [simbolos-y-fuentes/](simbolos-y-fuentes/README.md) | Conserva texto editable y convierte simbolos problematicos a vectores | Ejecuta `INSTALAR.bat` dentro de esa carpeta y usa el menu contextual del PDF |
| [giro-pdf/](giro-pdf/README.md) | Corrige PDF que Illustrator abre girados | Abre `Arreglar PDF.bat` dentro de esa carpeta |

Si necesitas ambas, corrige primero el giro y procesa el archivo `-FIXED.pdf`
con la herramienta de simbolos. Consulta el README de cada carpeta para instalar
sus dependencias y ver los comandos disponibles.

## Compatibilidad con instalaciones anteriores

El archivo `abrir_illustrator.bat` de la raiz redirige a `simbolos-y-fuentes/`.
Asi sigue funcionando el menu contextual instalado antes de reorganizar el
repositorio. Las nuevas instalaciones usan directamente la nueva carpeta.

## Verificacion

Desde la raiz del repositorio:

```powershell
python -m unittest discover -s simbolos-y-fuentes -p "test_*.py" -v
python -m compileall -q simbolos-y-fuentes giro-pdf
```

Las herramientas son aplicaciones locales para Windows. No requieren servidor
web. Los PDF generados y las caches de Python no se incluyen en Git.
