"""
Vectoriza un PDF (ULTIMO RECURSO).

La forma recomendada de abrir PDF de LaTeX/matematicas en Illustrator es instalar
las fuentes que faltan (ver  arreglar_y_abrir.py / clic derecho). Eso mantiene el
texto EDITABLE y no estropea nada.

Esto es solo para cuando quieras una copia "a prueba de balas" con el texto pasado
a CURVAS (vectores), que se ve igual en cualquier ordenador sin ninguna fuente.
A diferencia de la version antigua, ahora genera UN SOLO PDF compacto (no 24 SVG
enormes) y conserva las imagenes a su resolucion original (no hace capturas).

Uso:
  - Arrastra uno o varios PDF sobre  "Vectorizar PDF (arrastra aqui).bat"
  - O por linea de comandos:
        python vectorizar_pdf.py "archivo.pdf" [mas.pdf ...] [--out CARPETA] [--svg]
    --svg  -> ademas (o en vez de) el PDF, saca un SVG por pagina (como antes).
    Tambien puedes pasarle una CARPETA y convierte todos los PDF que haya.
"""
import sys, os, glob, unicodedata, tempfile
sys.stdout.reconfigure(encoding="utf-8")

try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        print("FALTA PyMuPDF. Instala con:  python -m pip install pymupdf")
        sys.exit(1)


def iter_pdfs(items):
    for a in items:
        if os.path.isdir(a):
            for p in sorted(glob.glob(os.path.join(a, "*.pdf"))):
                yield p
        elif os.path.isfile(a) and a.lower().endswith(".pdf"):
            yield a
        else:
            print("  (ignorado, no es un PDF):", a)


# ----------------------------------------------------------------------------
# VECTORIZACION SELECTIVA (lo normal): convierte a curvas SOLO el texto de las
# fuentes indicadas (matematicas/simbolos/exoticas) y deja TODO lo demas
# (texto editable, imagenes y graficos) intacto. Resultado: identico al original
# pero sin las fuentes que Illustrator no sabe sustituir.
# ----------------------------------------------------------------------------
def _rk(nombre, default):
    return getattr(pymupdf, nombre, default)

_IMG_NONE = _rk("PDF_REDACT_IMAGE_NONE", 0)
_IMG_REMOVE = _rk("PDF_REDACT_IMAGE_REMOVE", 1)
_GRA_NONE = _rk("PDF_REDACT_LINE_ART_NONE", 0)
_GRA_REMOVE = _rk("PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED", 2)
_TXT_REMOVE = _rk("PDF_REDACT_TEXT_REMOVE", 0)
_TXT_NONE = _rk("PDF_REDACT_TEXT_NONE", 1)


def _apply(page, **kw):
    # No degradar silenciosamente a una API que pueda borrar imagenes o texto.
    page.apply_redactions(**kw)


def _annot(page, r, shrink=0.0):
    r = pymupdf.Rect(r)
    r.normalize()
    if shrink:
        r += (shrink, shrink, -shrink, -shrink)
    if r.is_empty or r.is_infinite:
        return False
    try:
        page.add_redact_annot(r, fill=None, cross_out=False)
    except TypeError:
        page.add_redact_annot(r)
    return True


def _base(nombre):
    return nombre.split("+")[-1]


def es_simbolo_matematico(texto):
    """Selecciona operadores, letras griegas y glifos de codificacion dudosa.

    Los caracteres privados/sin Unicode se trazan usando el glifo del PDF,
    sin intentar adivinar que letra representan.
    """
    return any(unicodedata.category(c) in ("Sm", "Co") or c == "\ufffd"
               or 0x0370 <= ord(c) <= 0x03ff
               or 0x1f00 <= ord(c) <= 0x1fff
               or 0x1d400 <= ord(c) <= 0x1d7ff for c in texto)


def _analiza(page, es_vec):
    """Recorre el texto una vez y devuelve:
    (rects_char_vec, rects_span_vec, rects_span_novec, total_caracteres)."""
    vec_char, vec_span, novec_span, total = [], [], [], 0
    for b in page.get_text("rawdict").get("blocks", []):
        for l in b.get("lines", []):
            for s in l.get("spans", []):
                chars = s.get("chars", [])
                total += len(chars)
                r = pymupdf.Rect(s["bbox"])
                fuente_vector = es_vec(_base(s.get("font", "")))
                seleccion = [fuente_vector or es_simbolo_matematico(ch.get("c", ""))
                             for ch in chars]
                if chars and all(seleccion):
                    vec_span.append(r)
                    for ch in chars:
                        cb = ch.get("bbox")
                        if cb:
                            vec_char.append(pymupdf.Rect(cb))
                elif any(seleccion):
                    # Un mismo span puede mezclar prosa y simbolos: nunca quitarlo
                    # entero, ni al aislar los vectores ni al conservar el texto.
                    for ch, convertir in zip(chars, seleccion):
                        cb = pymupdf.Rect(ch["bbox"])
                        if convertir:
                            vec_char.append(cb)
                            vec_span.append(cb)
                        else:
                            novec_span.append(cb)
                else:
                    novec_span.append(r)
    return vec_char, vec_span, novec_span, total


def _vector_aislado(page_o, novec_span_rects):
    """PDF de 1 pagina con SOLO el texto a vectorizar, pasado a curvas (sin imagenes
    ni graficos, para no arrastrar cajas negras de imagenes con transparencia)."""
    with pymupdf.open() as src:
        src.insert_pdf(page_o.parent, from_page=page_o.number, to_page=page_o.number)
        vp = src[0]
        # 1a pasada: quitar el texto editable de la copia destinada a curvas.
        quitado = False
        for r in novec_span_rects:
            if _annot(vp, r, shrink=0.2):
                quitado = True
        if quitado:
            _apply(vp, images=_IMG_NONE, graphics=_GRA_NONE, text=_TXT_REMOVE)
        # Las imagenes originales nunca entran en SVG: conserva su transparencia.
        _annot(vp, vp.rect)
        _apply(vp, images=_IMG_REMOVE, graphics=_GRA_REMOVE, text=_TXT_NONE)
        svg = vp.get_svg_image(text_as_path=True)
    with pymupdf.open(stream=svg.encode("utf-8"), filetype="svg") as vdoc:
        return pymupdf.open("pdf", vdoc.convert_to_pdf())


def vectorizar_selectivo(path, vector_bases, out=None, log=print, todo=False):
    """Pasa a curvas fuentes en vector_bases y simbolos matematicos individuales.
    El resto del texto sigue editable; imagenes y graficos, intactos.
    Devuelve (ruta_salida, numero_de_glifos_vectorizados)."""
    vset = {_base(b) for b in vector_bases}

    def es_vec(nombre):
        return todo or _base(nombre) in vset

    if out is None:
        base = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(os.path.dirname(os.path.abspath(path)), base + "_para_illustrator.pdf")
    out = os.path.abspath(out)
    if (os.path.normcase(os.path.abspath(path)) == os.path.normcase(out)
            or (os.path.exists(out) and os.path.samefile(path, out))):
        raise ValueError("La salida no puede sobrescribir el PDF original.")
    tot = 0
    # Editar el documento completo en memoria conserva destinos entre paginas,
    # marcadores, metadatos y adjuntos. El archivo original nunca se guarda.
    with pymupdf.open(path) as salida:
        if salida.needs_pass:
            raise ValueError("El PDF requiere una contrasena. Guarda una copia desbloqueada.")
        for pno in range(salida.page_count):
            pg = salida[pno]
            rotacion = pg.rotation
            pg.set_rotation(0)
            try:
                vec_char, vec_span, novec_span, n_total = _analiza(pg, es_vec)
                if not vec_char:
                    continue
                casi_todo = n_total > 0 and len(vec_char) / n_total >= 0.9
                quitar = vec_span if casi_todo else vec_char
                enlaces = pg.get_links()
                with _vector_aislado(pg, novec_span) as vpdf:
                    for r in quitar:
                        _annot(pg, r)
                    _apply(pg, images=_IMG_NONE, graphics=_GRA_NONE, text=_TXT_REMOVE)
                    pg.show_pdf_page(pg.rect, vpdf, 0)
                # MuPDF elimina tambien enlaces solapados con una redaccion.
                existentes = {link["xref"] for link in pg.get_links()}
                for link in enlaces:
                    if link["xref"] not in existentes:
                        pg.insert_link({k: v for k, v in link.items() if k not in ("xref", "id")})
                tot += len(vec_char)
            except Exception as e:
                raise RuntimeError("No se pudo convertir la pagina %d: %s" % (pno + 1, e)) from e
            finally:
                pg.set_rotation(rotacion)
        # Sustituir una salida anterior solo cuando el nuevo PDF esta completo.
        fd, temporal = tempfile.mkstemp(prefix=".apdf-", suffix=".pdf", dir=os.path.dirname(out))
        os.close(fd)
        try:
            salida.save(temporal, garbage=4, deflate=True)
            os.replace(temporal, out)
        finally:
            if os.path.exists(temporal):
                os.remove(temporal)
    return out, tot


def vectorizar_a_pdf(path, out=None):
    """Convierte el PDF a UN solo PDF de curvas (texto -> vectores). Devuelve la ruta."""
    base = os.path.splitext(os.path.basename(path))[0]
    if out is None:
        out = os.path.join(os.path.dirname(os.path.abspath(path)), base + "_curvas.pdf")
    # El mismo aislamiento de texto evita convertir imagenes y graficos a SVG.
    salida, _ = vectorizar_selectivo(path, [], out=out, todo=True)
    return salida


def vectorizar_a_svg(path, outdir):
    """Un SVG por pagina (modo antiguo). Devuelve lista de rutas."""
    try:
        doc = pymupdf.open(path)
    except Exception as e:
        print("  ERROR al abrir", os.path.basename(path), "->", e)
        return []
    base = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(outdir, exist_ok=True)
    n = doc.page_count
    outs = []
    for i in range(n):
        try:
            svg = doc[i].get_svg_image(text_as_path=True)
        except Exception as e:
            print("  pagina", i + 1, "ERROR:", e)
            continue
        name = (base + "_vector.svg") if n == 1 else (base + "_p%02d.svg" % (i + 1))
        fp = os.path.join(outdir, name)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(svg)
        outs.append(fp)
    doc.close()
    return outs


def main():
    args = sys.argv[1:]
    out_override = None
    svg_mode = False
    items = []
    i = 0
    while i < len(args):
        if args[i] in ("--out", "-o") and i + 1 < len(args):
            out_override = args[i + 1]; i += 2; continue
        if args[i] == "--svg":
            svg_mode = True; i += 1; continue
        items.append(args[i]); i += 1

    if not items:
        print("Uso: arrastra PDFs sobre el .bat, o:")
        print('     python vectorizar_pdf.py "archivo.pdf" [--out CARPETA] [--svg]')
        return

    total = 0
    for pdf in iter_pdfs(items):
        print("PDF:", os.path.basename(pdf))
        if svg_mode:
            outdir = out_override or os.path.join(
                os.path.dirname(os.path.abspath(pdf)), "Vectorizado")
            outs = vectorizar_a_svg(pdf, outdir)
            for o in outs:
                print("   ->", o)
            total += len(outs)
        else:
            salida = vectorizar_a_pdf(pdf, out_override)
            if salida:
                print("   ->", salida)
                total += 1

    print("\nListo: %d archivo(s) creado(s)." % total)
    print("Abrelos en Illustrator (Archivo > Abrir). El texto esta en curvas.")


if __name__ == "__main__":
    main()
