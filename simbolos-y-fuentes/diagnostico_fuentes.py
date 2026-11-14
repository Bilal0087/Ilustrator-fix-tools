"""
Diagnostico de fuentes de un PDF -> por que se "colapsa" el texto en Illustrator.
Uso:  python diagnostico_fuentes.py "ruta1.pdf" "ruta2.pdf" ...
"""
import sys, os, re
sys.stdout.reconfigure(encoding="utf-8")
import winreg

try:
    import pymupdf as fitz  # PyMuPDF (nombre nuevo)
except ImportError:
    try:
        import fitz  # compatibilidad con versiones antiguas
    except ImportError:
        print("FALTA PyMuPDF.  Instala con:  python -m pip install pymupdf")
        sys.exit(1)

STYLE_WORDS = {
    "regular", "bold", "italic", "oblique", "medium", "light", "semibold",
    "black", "roman", "book", "thin", "heavy", "condensed", "narrow", "demi",
    "extrabold", "bolditalic", "mt", "ps", "psmt", "it", "bd", "rg", "normal",
}

def norm(s):
    s = s.split("+")[-1]
    return re.sub(r"[^A-Za-z0-9]", "", s).lower()

def core_tokens(basefont):
    name = basefont.split("+")[-1]
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)   # camelCase -> espacios
    name = re.sub(r"[-_,]", " ", name)
    toks = [t for t in re.split(r"\s+", name) if t]
    core = [t for t in toks if norm(t) not in STYLE_WORDS and not norm(t).isdigit()]
    return core or toks

def installed_fonts():
    names = set()
    for root, path in [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
        (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
    ]:
        try:
            k = winreg.OpenKey(root, path)
        except OSError:
            continue
        i = 0
        while True:
            try:
                nm, _val, _t = winreg.EnumValue(k, i)
            except OSError:
                break
            i += 1
            disp = re.sub(r"\(.*?\)", "", nm).strip()
            for part in re.split(r"[&]", disp):
                n = norm(part)
                if n:
                    names.add(n)
        winreg.CloseKey(k)
    return names

INSTALLED = installed_fonts()

def is_installed(basefont):
    full = norm(basefont)
    if len(full) >= 4:
        for ins in INSTALLED:
            if full == ins or full in ins or ins in full:
                return True
    core = "".join(norm(t) for t in core_tokens(basefont))
    if len(core) >= 3:
        for ins in INSTALLED:
            if core == ins or core in ins or ins in core:
                return True
    return False

KNOWN = [
    (r"lmroman|lmsans|lmmono|lmodern", "Latin Modern (GRATIS, CTAN/GUST) - tipica de LaTeX"),
    (r"cmr|cmmi|cmsy|cmex|cmbx|cmti|cmtt|cmss|computermodern", "Computer Modern (LaTeX) -> se cubre con Latin Modern (GRATIS)"),
    (r"msam|msbm|eufm|eufb|rsfs|wasy|stmary", "Simbolos matematicos LaTeX (AMS) -> van con Latin Modern/amsfonts (GRATIS)"),
    (r"nimbus|urw", "URW base35 (GRATIS)"),
    (r"stix|xits", "STIX / XITS (GRATIS)"),
    (r"texgyre|qtm|qpl|qhv|qcr|qag|qbk", "TeX Gyre (GRATIS)"),
    (r"cambriamath", "Cambria Math (viene con Windows/Office)"),
    (r"arial|calibri|times|cambria|verdana|tahoma|georgia|segoe", "Fuente de Windows/Office (suele estar instalada)"),
]

def known_note(basefont):
    low = basefont.lower()
    for pat, note in KNOWN:
        if re.search(pat, low):
            return note
    return ""


def fuentes_riesgo(path):
    """Devuelve (nombres, grupos): fuentes que probablemente rompan en Illustrator."""
    try:
        doc = fitz.open(path)
    except Exception:
        return [], {}
    nombres, vistos = [], set()
    for pno in range(doc.page_count):
        try:
            fonts = doc.get_page_fonts(pno, full=True)
        except Exception:
            continue
        for f in fonts:
            ftype, basefont = f[2], f[3]
            name = basefont.split("+")[-1]
            if name in vistos:
                continue
            vistos.add(name)
            if ftype == "Type3" or not is_installed(basefont):
                nombres.append(name)
    doc.close()
    grupos = {}
    for n in nombres:
        low = n.lower()
        if re.match(r"(cm|sf)[a-z0-9]", low) or "computermodern" in low:
            g = "Computer Modern / LaTeX"
        elif "nimbus" in low:
            g = "Nimbus (Helvetica libre)"
        elif "msbm" in low or "msam" in low or low.startswith("ms"):
            g = "Simbolos AMS (formulas)"
        elif "helvetica" in low:
            g = "Helvetica"
        else:
            g = "Otras"
        grupos.setdefault(g, set()).add(n)
    return nombres, grupos


def analyze(path):
    print("=" * 94)
    print("PDF:", os.path.basename(path))
    try:
        doc = fitz.open(path)
    except Exception as e:
        print("  ERROR al abrir:", e)
        return
    # scan rapido para detectar PDF escaneado (sin texto)
    try:
        t0 = doc[0].get_text("text") if doc.page_count else ""
        if len(t0.strip()) < 3:
            print("  AVISO: la 1a pagina casi no tiene texto -> podria ser un ESCANEO (imagen).")
    except Exception:
        pass

    seen = {}
    for pno in range(doc.page_count):
        try:
            fonts = doc.get_page_fonts(pno, full=True)
        except Exception:
            continue
        for f in fonts:
            xref = f[0]
            if xref in seen:
                continue
            ext, ftype, basefont = f[1], f[2], f[3]
            embedded = False
            try:
                fb = doc.extract_font(xref)
                embedded = bool(fb and fb[3])
            except Exception:
                embedded = ext not in ("", "n/a")
            subset = bool(re.match(r"^[A-Z]{6}\+", basefont))
            seen[xref] = (basefont, ftype, embedded, subset)

    if not seen:
        print("  (sin fuentes declaradas -> texto ya vectorizado, o PDF escaneado)")
        doc.close()
        return

    print("  {:<4}{:<8}{:<8}{:<9}{}".format("Emb", "Subset", "Tipo", "Inst?", "Fuente"))
    print("  " + "-" * 88)
    n_risk = 0
    for xref, (bf, ft, emb, sub) in sorted(seen.items(), key=lambda x: x[1][0].lower()):
        inst = is_installed(bf)
        risk = (ft == "Type3") or (not inst)
        if risk:
            n_risk += 1
        print("  {:<4}{:<8}{:<8}{:<9}{}{}".format(
            "si" if emb else "NO",
            "si" if sub else "no",
            ft,
            "si" if inst else "NO",
            bf,
            "   <== RIESGO" if risk else "",
        ))
        note = known_note(bf)
        if note:
            print("       -> " + note)
    print("  " + "-" * 88)
    print("  Resumen: {} fuente(s) con riesgo de colapso de {} en total.".format(n_risk, len(seen)))
    doc.close()

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Uso: python diagnostico_fuentes.py \"archivo.pdf\" [mas pdfs...]")
        sys.exit(0)
    for p in args:
        analyze(p)
    print("=" * 94)
    print("Leyenda: Emb=fuente incrustada | Subset=solo trae los caracteres usados |")
    print("         Inst?=esa fuente esta instalada en Windows | RIESGO=probable causa del colapso")
