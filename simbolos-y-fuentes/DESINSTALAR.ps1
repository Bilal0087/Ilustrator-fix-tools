# Quita el menu de clic derecho "Arreglar y abrir en Illustrator"
# y, si quieres, tambien las fuentes que instalo.
$dir = $PSScriptRoot
$base = "HKCU:\Software\Classes\SystemFileAssociations\.pdf\shell\ArreglarIllustrator"
if (Test-Path $base) {
    Remove-Item $base -Recurse -Force
    Write-Host "Menu 'Arreglar y abrir en Illustrator' quitado correctamente."
} else {
    Write-Host "No estaba instalado (nada que quitar)."
}

# Quitar tambien las fuentes instaladas y lo descargado (libera espacio).
Write-Host ""
Write-Host "Quitando las fuentes instaladas y borrando las descargas..."
try {
    python "$dir\fuentes.py" --borrar
} catch {
    Write-Host "  (no se pudieron quitar las fuentes automaticamente: $_)"
}
