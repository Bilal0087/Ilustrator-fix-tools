# Instala el menu de clic derecho "Arreglar y abrir en Illustrator" para archivos PDF.
# Solo para el usuario actual (NO necesita administrador). Reversible con DESINSTALAR.ps1
$ErrorActionPreference = "Stop"
$dir = $PSScriptRoot
$launcher = Join-Path $dir "abrir_illustrator.bat"

Write-Host "==============================================="
Write-Host " Instalando 'Arreglar y abrir en Illustrator'"
Write-Host "==============================================="

# 1) Asegurar dependencias de Python (PyMuPDF para leer PDF, fontTools para renombrar fuentes)
Write-Host "`n[1/3] Comprobando dependencias de Python..."
python -m pip install --quiet -r (Join-Path $dir "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias." }

# 2) Icono de Illustrator (opcional, para que se vea bonito en el menu)
Write-Host "`n[2/3] Buscando Illustrator..."
$icon = ""
$cand = Get-ChildItem "C:\Program Files\Adobe\Adobe Illustrator *\Support Files\Contents\Windows\Illustrator.exe" -ErrorAction Ignore |
        Sort-Object FullName -Descending | Select-Object -First 1
if ($cand) { $icon = $cand.FullName; Write-Host "      $icon" }
else { Write-Host "      (no encontrado; el menu se instala igual)" }

# 3) Registrar el menu contextual (HKCU -> sin admin)
Write-Host "`n[3/3] Registrando el menu de clic derecho..."
$base = "HKCU:\Software\Classes\SystemFileAssociations\.pdf\shell\ArreglarIllustrator"
New-Item -Path $base -Force | Out-Null
Set-ItemProperty -Path $base -Name "(default)" -Value "Arreglar y abrir en Illustrator"
if ($icon) { Set-ItemProperty -Path $base -Name "Icon" -Value $icon }
New-Item -Path "$base\command" -Force | Out-Null
$cmd = '"' + $launcher + '" "%1"'
Set-ItemProperty -Path "$base\command" -Name "(default)" -Value $cmd

Write-Host "`n-----------------------------------------------"
Write-Host "LISTO. Ya puedes:"
Write-Host "  Clic derecho sobre cualquier PDF ->"
Write-Host "  'Arreglar y abrir en Illustrator'"
Write-Host ""
Write-Host "(En Windows 11, si no lo ves, pulsa 'Mostrar mas opciones'.)"
Write-Host ""
Write-Host "La 1a vez que arregles un PDF se descargaran las fuentes (~10 MB) a:"
Write-Host "  %LOCALAPPDATA%\ArreglarPDF-Illustrator"
Write-Host "Para borrarlas y recuperar espacio: ejecuta  BORRAR_FUENTES.bat"
Write-Host "Para quitar el menu: clic derecho en DESINSTALAR.ps1 > Ejecutar con PowerShell"
Write-Host "-----------------------------------------------"
