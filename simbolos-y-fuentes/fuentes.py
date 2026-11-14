"""
Motor de fuentes: la SOLUCION de verdad para abrir PDF de LaTeX/matematicas
en Illustrator sin que el texto se colapse.

Idea (en vez de vectorizar y estropear el PDF):
  1. Mira que fuentes usa el PDF (Computer Modern, AMS, Helvetica/Nimbus, etc.).
  2. Descarga el equivalente GRATIS en OpenType (Latin Modern, Latin Modern Math,
     TeX Gyre, STIX) UNA sola vez y lo guarda en una carpeta conocida.
  3. Hace una copia de cada fuente RENOMBRADA con el nombre EXACTO que pide el PDF
     (CMR10, SFRM1200, Helvetica, MSBM10...) y la instala solo para tu usuario
     (sin administrador). Asi Illustrator la encuentra y el texto NO se colapsa.
  4. Luego se abre el PDF ORIGINAL (no se toca, no se rasteriza, no pesa).

Todo lo descargado/instalado vive en:
     %LOCALAPPDATA%\\ArreglarPDF-Illustrator
y se puede borrar entero cuando quieras (BORRAR_FUENTES.bat o  python fuentes.py --borrar).
"""
import sys, os, re, json, zipfile, shutil, ctypes
from ctypes import wintypes
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf  # versiones antiguas

import diagnostico_fuentes as diag
from fontTools.ttLib import TTFont

# ----------------------------------------------------------------------------
# Carpetas conocidas (todo borrable de un tiron)
# ----------------------------------------------------------------------------
APP_DIR   = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                         "ArreglarPDF-Illustrator")
FONTS_DIR = os.path.join(APP_DIR, "Fuentes")       # copias renombradas = lo instalado
CACHE_DIR = os.path.join(APP_DIR, "Descargas")     # zips + fuentes originales extraidas
MANIFEST  = os.path.join(APP_DIR, "fuentes_instaladas.json")

HKCU_FONTS = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"

# ----------------------------------------------------------------------------
# De donde se bajan las familias libres (equivalentes a las de LaTeX)
#   url   = enlace directo conocido
#   pagina= pagina de descarga (por si cambia la version, se busca ahi el .zip)
# ----------------------------------------------------------------------------
ARCHIVOS = {
    "lm": {
        "url":  "https://www.gust.org.pl/projects/e-foundry/latin-modern/download/Latin_Modern-otf-2_007-31_03_2026.zip",
        "pagina": "https://www.gust.org.pl/projects/e-foundry/latin-modern/download",
        "rx": r'href="([^"]*Latin_Modern-otf[^"]*\.zip)"',
    },
    "lmmath": {
        "url":  "https://www.gust.org.pl/projects/e-foundry/lm-math/download/latinmodern-math-1959.zip",
        "pagina": "https://www.gust.org.pl/projects/e-foundry/lm-math/download",
        "rx": r'href="([^"]*latinmodern-math[^"]*\.zip)"',
    },
    "texgyre": {
        "url":  "https://www.gust.org.pl/projects/e-foundry/tex-gyre/whole/tex_gyre-otf-2_609-31_03_2026.zip",
        "pagina": "https://www.gust.org.pl/projects/e-foundry/tex-gyre/whole",
        "rx": r'href="([^"]*tex_gyre-otf[^"]*\.zip)"',
    },
    # STIX se baja archivo a archivo (no zip)
    "stix": {
        "raw": "https://raw.githubusercontent.com/stipub/stixfonts/master/fonts/opentype/public/stix/",
        "files": ["STIX-Regular.otf", "STIX-Bold.otf", "STIX-Italic.otf",
                  "STIX-BoldItalic.otf", "STIXMath-Regular.otf"],
    },
}

UA = {"User-Agent": "Mozilla/5.0 (ArreglarPDF-Illustrator)"}


# ----------------------------------------------------------------------------
# 1) ANALISIS del PDF: que fuentes hay y cuales fallarian
# ----------------------------------------------------------------------------
def escanear(pdf):
    """Lista de fuentes unicas del PDF con su tipo, formato y si esta instalada."""
    doc = pymupdf.open(pdf)
    vistos, fuentes = set(), []
    for pno in range(doc.page_count):
        try:
            page_fonts = doc.get_page_fonts(pno, full=True)
        except Exception:
            continue
        for f in page_fonts:
            xref, ftype, basefont = f[0], f[2], f[3]
            base = basefont.split("+")[-1]
            if base in vistos:
                continue
            vistos.add(base)
            try:
                _n, eext, _t, buf = doc.extract_font(xref)
            except Exception:
                eext, buf = "", b""
            fuentes.append({
                "base": base,
                "tipo": ftype,
                "ext": eext,
                "xref": xref,
                "embedded": bool(buf),
                "instalada": diag.is_installed(basefont),
            })
    doc.close()
    return fuentes


# ----------------------------------------------------------------------------
# 2) CLASIFICAR un nombre de fuente -> que familia libre usar y con que estilo
# ----------------------------------------------------------------------------
def _estilo(low):
    bold = bool(re.search(r"(bold|black|heavy|\bbx|cmbx|sfbx|-bd\b|semibold|demi)", low))
    ital = bool(re.search(r"(italic|oblique|slant|reguital|cmti|sfti|cmsl|-it\b|ital)", low))
    return bold, ital


def _tam(low):
    """Tamano optico aproximado. CM usa el numero tal cual; CM-super (sf*) usa pt*100."""
    nums = re.findall(r"\d+", low)
    if not nums:
        return 10
    n = int(nums[-1])
    if (low.startswith("sf") or n >= 100):
        return max(5, round(n / 100.0))
    return n if n else 10


def clasificar(base):
    """Devuelve dict {archive, key, size, bold, italic, math} o None si no se sabe mapear."""
    low = re.sub(r"[^a-z0-9]", "", base.lower())
    bold, ital = _estilo(base.lower())
    size = _tam(low)

    # --- simbolos / matematicas (encaje aproximado: puede no ser exacto) ---
    if re.search(r"(cmmi|cmsy|cmex|cmbsy|cmmib|msam|msbm|eufm|eufb|eurm|eusm|eusb|"
                 r"rsfs|wasy|stmary|bbold|dsrom|mathjax)", low):
        return {"archive": "lmmath", "key": "lm-math", "size": size,
                "bold": bold, "italic": ital, "math": True}

    # --- sans ---
    if re.search(r"(cmss|sfss|lmsans)", low):
        return {"archive": "lm", "key": "lm-sans", "size": size, "bold": bold, "italic": ital, "math": False}
    if re.search(r"(helvetica|nimbussan|arial|heros|phv)", low):
        return {"archive": "texgyre", "key": "tg-heros", "size": size, "bold": bold, "italic": ital, "math": False}
    if re.search(r"(avantgarde|adventor)", low):
        return {"archive": "texgyre", "key": "tg-adventor", "size": size, "bold": bold, "italic": ital, "math": False}

    # --- monoespaciada ---
    if re.search(r"(cmtt|sftt|lmmono|cmsltt|cmtex|cmvtt)", low):
        return {"archive": "lm", "key": "lm-mono", "size": size, "bold": bold, "italic": ital, "math": False}
    if re.search(r"(courier|nimbusmon|cursor|pcr)", low):
        return {"archive": "texgyre", "key": "tg-cursor", "size": size, "bold": bold, "italic": ital, "math": False}

    # --- serif ---
    if re.search(r"(times|nimbusrom|termes|ptm)", low):
        return {"archive": "texgyre", "key": "tg-termes", "size": size, "bold": bold, "italic": ital, "math": False}
    if re.search(r"(palatino|pagella)", low):
        return {"archive": "texgyre", "key": "tg-pagella", "size": size, "bold": bold, "italic": ital, "math": False}
    if re.search(r"(bookman|bonum)", low):
        return {"archive": "texgyre", "key": "tg-bonum", "size": size, "bold": bold, "italic": ital, "math": False}
    if re.search(r"(schoolbook|century|schola)", low):
        return {"archive": "texgyre", "key": "tg-schola", "size": size, "bold": bold, "italic": ital, "math": False}
    if re.search(r"(stix|xits)", low):
        return {"archive": "stix", "key": "stix-text", "size": size, "bold": bold, "italic": ital, "math": False}
    if re.search(r"(cmr|cmbx|cmti|cmsl|cmcsc|cmdunh|cmff|cmfib|cmb\b|sfrm|sfbx|sfti|sfsl|"
                 r"lmroman|computermodern|cmu)", low):
        return {"archive": "lm", "key": "lm-roman", "size": size, "bold": bold, "italic": ital, "math": False}

    return None


# ----------------------------------------------------------------------------
# 3) DESCARGA + extraccion de las familias (cacheado: solo la 1a vez)
# ----------------------------------------------------------------------------
def _descargar(url, destino, log):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r, open(destino, "wb") as f:
        shutil.copyfileobj(r, f)
    return os.path.getsize(destino)


def _resolver_url(info, log):
    """Prueba el enlace directo; si falla, busca el .zip actual en la pagina."""
    try:
        req = urllib.request.Request(info["url"], headers=UA, method="HEAD")
        urllib.request.urlopen(req, timeout=30).close()
        return info["url"]
    except Exception:
        pass
    try:
        req = urllib.request.Request(info["pagina"], headers=UA)
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        m = re.search(info["rx"], html, re.I)
        if m:
            href = m.group(1)
            if href.startswith("http"):
                return href
            if href.startswith("/"):
                from urllib.parse import urljoin
                return urljoin(info["pagina"], href)
            return info["pagina"].rsplit("/", 1)[0] + "/" + href
    except Exception as e:
        log("      (no pude resolver enlace actualizado: %s)" % e)
    return info["url"]


def asegurar_familia(archive, log):
    """Devuelve la carpeta con los .otf de esa familia, bajandola si hace falta."""
    dest = os.path.join(CACHE_DIR, archive)
    if os.path.isdir(dest) and any(n.lower().endswith(".otf") for n in os.listdir(dest)):
        return dest
    os.makedirs(dest, exist_ok=True)
    info = ARCHIVOS[archive]

    if archive == "stix":
        log("      Descargando STIX...")
        ok = 0
        for fn in info["files"]:
            try:
                _descargar(info["raw"] + fn, os.path.join(dest, fn), log)
                ok += 1
            except Exception as e:
                log("        (no se pudo bajar %s: %s)" % (fn, e))
        return dest if ok else None

    url = _resolver_url(info, log)
    zp = os.path.join(CACHE_DIR, archive + ".zip")
    if not (os.path.exists(zp) and os.path.getsize(zp) > 500000):
        log("      Descargando %s ..." % archive)
        _descargar(url, zp, log)
    with zipfile.ZipFile(zp) as z:
        for n in z.namelist():
            if n.lower().endswith((".otf", ".ttf")):
                with z.open(n) as src, open(os.path.join(dest, os.path.basename(n)), "wb") as out:
                    shutil.copyfileobj(src, out)
    # el .zip ya no hace falta (los .otf extraidos son lo que se usa) -> libera espacio
    try:
        os.remove(zp)
    except OSError:
        pass
    return dest


# ----------------------------------------------------------------------------
# 4) ELEGIR el archivo .otf concreto dentro de la familia
# ----------------------------------------------------------------------------
def _primero_que_exista(carpeta, nombres):
    for n in nombres:
        p = os.path.join(carpeta, n)
        if os.path.exists(p):
            return p
    return None


def _lm_estilos(bold, ital, oblicua=False):
    it = "oblique" if oblicua else "italic"
    if bold and ital:
        return ["bold" + it, "boldoblique", "bolditalic", bold and "bold", it, "oblique", "regular"]
    if bold:
        return ["bold", "regular"]
    if ital:
        return [it, "italic", "oblique", "regular"]
    return ["regular"]


def _lm_por_tam(carpeta, prefijo, size, estilos):
    disponibles = {}
    for fn in os.listdir(carpeta):
        m = re.match(re.escape(prefijo) + r"(\d+)-", fn.lower())
        if m:
            disponibles.setdefault(int(m.group(1)), True)
    tams = sorted(disponibles, key=lambda s: (abs(s - size), s)) or [10]
    for t in tams:
        for est in estilos:
            if not est:
                continue
            p = os.path.join(carpeta, "%s%d-%s.otf" % (prefijo, t, est))
            if os.path.exists(p):
                return p
    # ultimo recurso: cualquiera del prefijo
    for fn in sorted(os.listdir(carpeta)):
        if fn.lower().startswith(prefijo) and fn.lower().endswith(".otf"):
            return os.path.join(carpeta, fn)
    return None


def _tg_estilos(bold, ital):
    if bold and ital:
        return ["bolditalic", "bold", "italic", "regular"]
    if bold:
        return ["bold", "regular"]
    if ital:
        return ["italic", "regular"]
    return ["regular"]


def elegir_otf(carpeta, cls):
    key, size, bold, ital = cls["key"], cls["size"], cls["bold"], cls["italic"]
    if key == "lm-roman":
        return _lm_por_tam(carpeta, "lmroman", size, _lm_estilos(bold, ital))
    if key == "lm-sans":
        return _lm_por_tam(carpeta, "lmsans", size, _lm_estilos(bold, ital, oblicua=True))
    if key == "lm-mono":
        return _lm_por_tam(carpeta, "lmmono", size, _lm_estilos(bold, ital, oblicua=False))
    if key == "lm-math":
        return _primero_que_exista(carpeta, ["latinmodern-math.otf"]) or \
               _lm_por_tam(carpeta, "latinmodern", size, ["math"])
    tg = {"tg-heros": "texgyreheros", "tg-termes": "texgyretermes",
          "tg-cursor": "texgyrecursor", "tg-pagella": "texgyrepagella",
          "tg-bonum": "texgyrebonum", "tg-schola": "texgyreschola",
          "tg-adventor": "texgyreadventor"}.get(key)
    if tg:
        cand = ["%s-%s.otf" % (tg, e) for e in _tg_estilos(bold, ital)]
        return _primero_que_exista(carpeta, cand)
    if key == "stix-text":
        est = {(0, 0): "STIX-Regular.otf", (1, 0): "STIX-Bold.otf",
               (0, 1): "STIX-Italic.otf", (1, 1): "STIX-BoldItalic.otf"}[(int(bold), int(ital))]
        return _primero_que_exista(carpeta, [est, "STIX-Regular.otf"])
    return None


# ----------------------------------------------------------------------------
# 5) RENOMBRAR una copia con el nombre que pide el PDF
# ----------------------------------------------------------------------------
def _nombre_archivo(base):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", base)
    return "APDF_" + safe + ".otf"


def renombrar_otf(src, nuevo_nombre, destino):
    f = TTFont(src)
    name = f["name"]
    ps = re.sub(r"[^A-Za-z0-9-]", "", nuevo_nombre) or "Fuente"
    sub = "Regular"
    for nid, val in [(1, nuevo_nombre), (2, sub), (3, ps), (4, nuevo_nombre),
                     (6, ps), (16, nuevo_nombre), (17, sub)]:
        name.setName(val, nid, 3, 1, 0x409)   # Windows / ingles
        name.setName(val, nid, 1, 0, 0)        # Mac
    if "CFF " in f:
        cff = f["CFF "].cff
        try:
            td = cff[cff.fontNames[0]]
            td.FullName = nuevo_nombre
            td.FamilyName = nuevo_nombre
        except Exception:
            pass
        cff.fontNames[0] = ps
    f.save(destino)
    f.close()


# ----------------------------------------------------------------------------
# 6) INSTALAR / DESINSTALAR para el usuario actual (sin administrador)
# ----------------------------------------------------------------------------
def _gdi():
    return ctypes.WinDLL("gdi32"), ctypes.WinDLL("user32")


def _broadcast_fontchange():
    try:
        user = ctypes.WinDLL("user32")
        HWND_BROADCAST, WM_FONTCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x001D, 0x0002
        res = wintypes.DWORD()
        user.SendMessageTimeoutW(HWND_BROADCAST, WM_FONTCHANGE, 0, 0,
                                 SMTO_ABORTIFHUNG, 1000, ctypes.byref(res))
    except Exception:
        pass


def _leer_manifest():
    if os.path.exists(MANIFEST):
        try:
            with open(MANIFEST, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"fuentes": []}


def _guardar_manifest(m):
    os.makedirs(APP_DIR, exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)


def instalar_fuente(path, display):
    """Registra la fuente para el usuario actual y la carga en la sesion."""
    gdi, _user = _gdi()
    gdi.AddFontResourceW(ctypes.c_wchar_p(path))
    import winreg
    valor = display + " (OpenType)"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, HKCU_FONTS) as k:
        winreg.SetValueEx(k, valor, 0, winreg.REG_SZ, path)
    return valor


def desinstalar_todo(log=print, borrar_cache=True):
    m = _leer_manifest()
    import winreg
    gdi, _user = _gdi()
    quitadas = 0
    for fu in m.get("fuentes", []):
        try:
            gdi.RemoveFontResourceW(ctypes.c_wchar_p(fu["file"]))
        except Exception:
            pass
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, HKCU_FONTS, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, fu["reg"])
        except Exception:
            pass
        try:
            if os.path.exists(fu["file"]):
                os.remove(fu["file"])
        except Exception:
            pass
        quitadas += 1
    _broadcast_fontchange()
    try:
        if os.path.exists(MANIFEST):
            os.remove(MANIFEST)
    except Exception:
        pass
    if borrar_cache:
        for d in (FONTS_DIR, CACHE_DIR):
            shutil.rmtree(d, ignore_errors=True)
    log("Quitadas %d fuente(s) instaladas por esta herramienta." % quitadas)
    log("Carpeta: %s" % APP_DIR)
    return quitadas


# ----------------------------------------------------------------------------
# 7) PROVISION: todo junto para un PDF
# ----------------------------------------------------------------------------
def provision(pdf, log=print, dry=False):
    os.makedirs(FONTS_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    manifest = _leer_manifest()
    ya_prov = {fu["base"]: fu for fu in manifest.get("fuentes", [])}

    fuentes = escanear(pdf)
    res = {"instaladas": [], "ya": [], "no_mapeadas": [], "tipo3": [],
           "ok_sistema": [], "familias": set()}

    # 1) decidir que hace falta
    plan = []
    for fo in fuentes:
        base = fo["base"]
        if fo["instalada"] and base not in ya_prov:
            res["ok_sistema"].append(base)
            continue
        if base in ya_prov and os.path.exists(ya_prov[base]["file"]):
            res["ya"].append(base)
            continue
        if fo["tipo"] == "Type3":
            res["tipo3"].append(base)
            continue
        cls = clasificar(base)
        if not cls:
            res["no_mapeadas"].append(base)
            continue
        plan.append((base, cls))
        res["familias"].add(cls["archive"])

    if dry:
        res["plan"] = [(b, c["key"], c["size"], c["bold"], c["italic"]) for b, c in plan]
        return res

    # 2) bajar las familias que se necesiten (una sola vez)
    carpetas = {}
    for arch in res["familias"]:
        try:
            carpetas[arch] = asegurar_familia(arch, log)
        except Exception as e:
            log("      ERROR bajando familia %s: %s" % (arch, e))
            carpetas[arch] = None

    # 3) renombrar + instalar cada fuente
    nuevos = []
    for base, cls in plan:
        carpeta = carpetas.get(cls["archive"])
        if not carpeta:
            res["no_mapeadas"].append(base)
            continue
        src = elegir_otf(carpeta, cls)
        if not src:
            res["no_mapeadas"].append(base)
            continue
        destino = os.path.join(FONTS_DIR, _nombre_archivo(base))
        try:
            renombrar_otf(src, base, destino)
            reg = instalar_fuente(destino, base)
            nuevos.append({"base": base, "file": destino, "reg": reg,
                           "origen": os.path.basename(src), "math": cls["math"]})
            res["instaladas"].append(base)
        except Exception as e:
            log("      ERROR instalando %s: %s" % (base, e))
            res["no_mapeadas"].append(base)

    if nuevos:
        manifest.setdefault("fuentes", [])
        # evita duplicados por base
        existentes = {fu["base"] for fu in manifest["fuentes"]}
        manifest["fuentes"].extend(fu for fu in nuevos if fu["base"] not in existentes)
        _guardar_manifest(manifest)
        _broadcast_fontchange()

    res["familias"] = sorted(res["familias"])
    res["math_instaladas"] = [n["base"] for n in nuevos if n["math"]]
    return res


# ----------------------------------------------------------------------------
# 8) PLAN HIBRIDO: decidir por fuente KEEP (texto editable) o VECTOR (a curvas)
# ----------------------------------------------------------------------------
def es_vectorizable(fo, editable=False):
    """Vectoriza fuentes de simbolos o sin sustituto disponible.

    Type0 describe la codificacion, no si una fuente contiene matematicas.
    editable se conserva por compatibilidad: el texto instalado se mantiene
    editable tambien en el modo predeterminado.
    """
    base = fo["base"]
    tipo = fo.get("tipo", "")
    if tipo == "Type3":          # son dibujos, no fuentes
        return True
    low = re.sub(r"[^a-z0-9]", "", base.lower())
    if any(nombre in low for nombre in
           ("math", "symbol", "dingbat", "wingding", "webding", "cmsy", "cmex")):
        return True
    cls = clasificar(base)
    if cls and cls.get("math"):  # simbolos matematicos: sin equivalente fiel por nombre
        return True
    if cls and not cls.get("math"):
        return False             # familia de texto LaTeX que SI sabemos proveer
    if fo.get("instalada"):
        return False             # tambien para texto Office en fuentes Type0/CID
    return True                  # sin equivalente fiel -> a curvas


def plan_hibrido(pdf, editable=False, log=print, dry=False):
    """Decide por fuente y, salvo dry, instala las KEEP de texto que falten.
    Devuelve dict con 'vector' (bases a pasar a curvas) y el detalle de las KEEP."""
    if not dry:
        os.makedirs(FONTS_DIR, exist_ok=True)
        os.makedirs(CACHE_DIR, exist_ok=True)
    fuentes = escanear(pdf)
    res = {"vector": set(), "keep_sistema": [], "instaladas": [], "ya": [],
           "tipo3": [], "familias": set()}
    manifest = _leer_manifest()
    ya_prov = {fu["base"]: fu for fu in manifest.get("fuentes", [])}

    plan = []
    for fo in fuentes:
        base = fo["base"]
        if es_vectorizable(fo, editable):
            res["vector"].add(base)
            if fo.get("tipo") == "Type3":
                res["tipo3"].append(base)
            continue
        if fo["instalada"]:
            res["keep_sistema"].append(base); continue
        if base in ya_prov and os.path.exists(ya_prov[base]["file"]):
            res["ya"].append(base); continue
        cls = clasificar(base)
        if cls and not cls["math"]:
            plan.append((base, cls)); res["familias"].add(cls["archive"])
        else:
            res["vector"].add(base)   # no sabemos instalarla -> a curvas

    if dry:
        res["plan"] = [(b, c["key"], c["size"], c["bold"], c["italic"]) for b, c in plan]
        res["vector"] = sorted(res["vector"]); res["familias"] = sorted(res["familias"])
        return res

    # instalar las familias KEEP de texto que falten (reutiliza el motor de provision)
    carpetas = {}
    for arch in res["familias"]:
        try:
            carpetas[arch] = asegurar_familia(arch, log)
        except Exception as e:
            log("      ERROR bajando familia %s: %s" % (arch, e)); carpetas[arch] = None
    nuevos = []
    for base, cls in plan:
        carpeta = carpetas.get(cls["archive"])
        src = elegir_otf(carpeta, cls) if carpeta else None
        if not src:
            res["vector"].add(base); continue
        destino = os.path.join(FONTS_DIR, _nombre_archivo(base))
        try:
            renombrar_otf(src, base, destino)
            reg = instalar_fuente(destino, base)
            nuevos.append({"base": base, "file": destino, "reg": reg,
                           "origen": os.path.basename(src), "math": False})
            res["instaladas"].append(base)
        except Exception as e:
            log("      ERROR instalando %s: %s" % (base, e)); res["vector"].add(base)
    if nuevos:
        manifest.setdefault("fuentes", [])
        existentes = {fu["base"] for fu in manifest["fuentes"]}
        manifest["fuentes"].extend(fu for fu in nuevos if fu["base"] not in existentes)
        _guardar_manifest(manifest); _broadcast_fontchange()

    res["vector"] = sorted(res["vector"])
    res["familias"] = sorted(res["familias"])
    return res


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def main():
    args = sys.argv[1:]
    if "--borrar" in args:
        desinstalar_todo()
        return
    dry = "--dry" in args
    editable = "--editable" in args
    pdfs = [a for a in args if not a.startswith("--")]
    if not pdfs:
        print("Uso: python fuentes.py \"archivo.pdf\" [--dry] [--editable]")
        print("     python fuentes.py --borrar     (quita todas las fuentes instaladas)")
        return
    for pdf in pdfs:
        print("=" * 64)
        print("PDF:", os.path.basename(pdf))
        r = plan_hibrido(pdf, editable=editable, dry=dry)
        if dry:
            print("  PLAN (no instala nada):")
            print("  -> instalar como TEXTO editable:")
            for b, key, size, bold, ital in r.get("plan", []):
                print("       %-24s -> %-10s size=%-3s %s%s"
                      % (b, key, size, "B" if bold else "", "I" if ital else ""))
            print("  -> ya editables (sistema/instaladas):",
                  ", ".join(sorted(set(r["keep_sistema"]) | set(r["ya"]))) or "-")
            print("  -> A CURVAS (vectores):", ", ".join(r["vector"]) or "-")
        else:
            print("  Instaladas :", ", ".join(r["instaladas"]) or "-")
            print("  Ya editables:", ", ".join(sorted(set(r["keep_sistema"]) | set(r["ya"]))) or "-")
            print("  A curvas   :", ", ".join(r["vector"]) or "-")
    print("Carpeta de fuentes:", APP_DIR)


if __name__ == "__main__":
    main()
