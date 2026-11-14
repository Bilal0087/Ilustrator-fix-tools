"""
Arreglar y abrir en Illustrator (proceso automatico).
Lo llama el menu de clic derecho sobre un PDF.

QUE HACE (solucion HIBRIDA: fiel al original y sin cosas raras):
   1) Mira que fuentes usa el PDF y decide por cada una:
        - TEXTO EDITABLE: las que sabemos proveer con fidelidad (familias LaTeX:
          Computer Modern->Latin Modern, Helvetica/Nimbus->TeX Gyre, Times...).
          Se descarga el equivalente GRATIS una sola vez, se renombra con el
          nombre EXACTO que pide el PDF y se instala para tu usuario (sin admin).
        - A CURVAS (vectores): lo que Illustrator NO sustituye bien -> simbolos
          matematicos, Type3 y fuentes sin sustituto disponible. Asi se ve
          IDENTICO al original aunque no sea editable ese trozo.
   2) Crea una copia "<nombre>_para_illustrator.pdf" con ese criterio: el texto
      normal sigue editable, las matematicas van en vectores, e imagenes y
      graficos quedan intactos. Si no hay nada que vectorizar, abre el original.
   3) La abre en Illustrator. Nada se rasteriza.

Todo lo descargado va a una carpeta que puedes borrar cuando quieras:
   %LOCALAPPDATA%\\ArreglarPDF-Illustrator   (o ejecuta BORRAR_FUENTES.bat)

Uso:  python arreglar_y_abrir.py "archivo.pdf" [opciones]
      --no-open     no lanza Illustrator (solo prepara el PDF)
      --editable    compatible con versiones anteriores; el texto instalado
                    ya se conserva editable por defecto
      --vector      pasa TODO el texto a curvas (ultimo recurso, nada editable)
      --solo-fuentes  instala las fuentes KEEP y no crea ni abre nada
"""
import sys, os, subprocess, glob, time
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fuentes as fz
import vectorizar_pdf as vec


def encontrar_illustrator():
    # 1) Registro: App Paths
    try:
        import winreg
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                k = winreg.OpenKey(
                    root, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Illustrator.exe")
                val, _ = winreg.QueryValueEx(k, None)
                winreg.CloseKey(k)
                if val and os.path.exists(val):
                    return val
            except OSError:
                pass
    except Exception:
        pass
    # 2) Buscar en Archivos de programa (version mas nueva primero)
    pats = [
        r"C:\Program Files\Adobe\Adobe Illustrator *\Support Files\Contents\Windows\Illustrator.exe",
        r"C:\Program Files (x86)\Adobe\Adobe Illustrator *\Support Files\Contents\Windows\Illustrator.exe",
    ]
    hits = []
    for p in pats:
        hits += glob.glob(p)
    hits.sort(reverse=True)
    return hits[0] if hits else None


def illustrator_abierto():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Illustrator.exe"],
                             capture_output=True, text=True, timeout=10).stdout
        return "Illustrator.exe" in out
    except Exception:
        return False


def abrir(ai, archivo, no_open):
    if no_open:
        print("      [PRUEBA] No lanzo Illustrator. Abriria:", archivo)
        return
    if not ai:
        print("      No encontre Illustrator.exe. Abro la carpeta.")
        try:
            os.startfile(os.path.dirname(archivo))
        except Exception:
            pass
        return
    try:
        subprocess.Popen([ai, archivo])
        print("      -> Abriendo:", os.path.basename(archivo))
    except Exception as e:
        print("      Error al abrir Illustrator:", e)


def flujo_hibrido(pdf, no_open, solo_fuentes, editable):
    """El flujo normal: texto editable donde se puede, lo demas a curvas, de forma
    que el PDF se vea IDENTICO al original en Illustrator sin cosas raras."""
    print("\n[1/3] Analizando las fuentes del PDF...")
    r = fz.plan_hibrido(pdf, editable=editable, log=lambda m: print(m))
    editable_total = len(r["keep_sistema"]) + len(r["instaladas"]) + len(r["ya"])
    if r["instaladas"]:
        print("      Instaladas para texto editable: {}{}".format(
            ", ".join(sorted(r["instaladas"])[:8]),
            " ..." if len(r["instaladas"]) > 8 else ""))
    if editable_total:
        print("      Fuentes que quedan como TEXTO EDITABLE: {}".format(editable_total))
    if r["vector"]:
        print("      A CURVAS (no editable, pero IDENTICO al original): {}{}".format(
            ", ".join(r["vector"][:10]), " ..." if len(r["vector"]) > 10 else ""))
        print("      (matematicas/simbolos/fuentes que Illustrator no sustituye bien)")
    else:
        print("      Fuentes de texto editables; se revisaran los simbolos por caracter.")

    if solo_fuentes:
        print("\n(--solo-fuentes) No creo ni abro ningun PDF.")
        return

    print("\n[2/3] Preparando el PDF para Illustrator...")
    salida, n = vec.vectorizar_selectivo(pdf, r["vector"], log=lambda m: print(m))
    print("      Creado: {}  ({} glifos pasados a curvas)".format(os.path.basename(salida), n))

    print("\n[3/3] Abriendo en Illustrator...")
    if illustrator_abierto() and not no_open and r["instaladas"]:
        print("      *** Illustrator ya estaba ABIERTO: cierralo del todo y vuelve a")
        print("          abrir el archivo, si no, no vera las fuentes recien instaladas. ***")
    abrir(encontrar_illustrator(), salida, no_open)


def flujo_vector(pdf, no_open):
    import vectorizar_pdf as vec
    print("\n[1/2] (--vector) Vectorizando a un PDF de curvas (texto NO editable)...")
    salida = vec.vectorizar_a_pdf(pdf)
    if not salida:
        print("      No se pudo vectorizar (quiza es un PDF escaneado).")
        time.sleep(5)
        return
    print("      Creado:", salida)
    print("\n[2/2] Abriendo en Illustrator...")
    abrir(encontrar_illustrator(), salida, no_open)


def main():
    raw = sys.argv[1:]
    no_open = "--no-open" in raw
    vector = "--vector" in raw
    solo_fuentes = "--solo-fuentes" in raw
    editable = "--editable" in raw
    files = [a for a in raw if not a.startswith("--")]

    if not files:
        print("Arrastra un PDF o pasa la ruta como argumento.")
        time.sleep(3)
        return
    pdf = files[0]
    if not (os.path.isfile(pdf) and pdf.lower().endswith(".pdf")):
        print("No es un PDF valido:", pdf)
        time.sleep(3)
        return

    print("=" * 66)
    print(" ARREGLAR PDF PARA ILLUSTRATOR")
    print("=" * 66)
    print("Archivo:", os.path.basename(pdf))

    if vector:
        flujo_vector(pdf, no_open)
    else:
        flujo_hibrido(pdf, no_open, solo_fuentes, editable)

    print("\nHecho.")
    print("Las fuentes descargadas estan en:  %s" % fz.APP_DIR)
    print("Para borrarlas y recuperar espacio: ejecuta  BORRAR_FUENTES.bat")
    if not no_open:
        time.sleep(4)


if __name__ == "__main__":
    main()
