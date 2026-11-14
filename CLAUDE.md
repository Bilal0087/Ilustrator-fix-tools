# CLAUDE.md

## Current behavior (supersedes older policy notes below)

The hybrid default preserves installed body-text fonts, including Type0/CID
Office fonts. Type0 alone is not a reason to outline text. Math/symbol font
families are outlined even when installed. Within other fonts, operators, Greek
letters, mathematical alphanumerics and private/unmapped characters are outlined
individually; ordinary text remains editable. Unknown unavailable fonts retain
the outline fallback. `--editable` is now a compatibility flag.

The selective pass runs even with an empty font outline list, because symbols
can share a font with body text. `--solo-fuentes` exits before PDF conversion.
Install with `python -m pip install -r requirements.txt`; PyMuPDF 1.28.2 is pinned
after reproducing text-position loss with 2.0. Run `python -m unittest -v test_hibrido`
for classification, character-position, rendering and image-preservation checks.
See `README.md` for current usage. The older description below documents the
architecture but its Office/Type0 policy and statement that no tests exist are
obsolete. Do not restore those policies.

The selective engine now edits the whole document in memory to preserve internal
links and metadata. It temporarily clears each page rotation for processing and
restores it afterwards. Both full and selective outlining use text-only SVG;
original images and graphics stay in the PDF. Page failures abort without
replacing previous output, and saving uses a temporary file plus atomic replace.
`--dry` creates no directories. Older notes about skipping rotated pages,
reassembling documents page by page, or dropping internal links are obsolete.

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A small Windows (no-admin) tool that fixes PDFs whose text **breaks / "collapses" when
opened in Adobe Illustrator** — classically LaTeX/math exam PDFs, but also Office/PowerPoint
exports. All UI text and comments are in Spanish (the user's language) — keep new strings in
Spanish.

The breakage happens because the PDF embeds **subsetted fonts Illustrator doesn't have** and
substitutes badly on open/edit: Computer Modern Type1 (`CMR*/CMMI*/CMSY*/CMSS*/CMEX*`),
CM-super `SF*`, AMS symbols `MSBM*/MSAM*`, URW `NimbusSanL`/`Helvetica`, and — in Office
exports — Type0/CID subsets (`ArialMT`, `SymbolMT`, `Calibri`, `Aptos`, `CambriaMath`,
`Wingdings`, …).

## The approach — HYBRID: keep editable what we control, vectorize the rest (do not regress)

Guiding principle: **we can only guarantee an identical result in Illustrator for fonts we
control.** This repo's environment can't actually verify how Illustrator substitutes fonts, so
each font is sorted into one of two buckets and the output PDF is built accordingly:

- **KEEP (stays editable text):** fonts we can provide faithfully — the LaTeX families we
  install by exact name (Computer Modern→Latin Modern, Helvetica/Nimbus→TeX Gyre Heros,
  Times→Termes, sans→LM Sans, …). In `--editable` mode, also fonts already installed system-wide.
- **VECTORIZE (text → curves):** everything else — math/symbol fonts (no faithful name-match),
  `Type3` (drawings), `Type0`/CID subsets, Office fonts, anything we can't provision. These are
  turned to outlines so they render **identically** in Illustrator with no font substitution.

Pipeline per PDF (`arreglar_y_abrir.py`, the default/right-click flow):
1. Scan fonts, classify KEEP vs VECTORIZE (`fuentes.plan_hibrido` / `es_vectorizable`).
2. Install the KEEP LaTeX families that are missing (download the free OTF once, cached, rewrite
   the name table to the exact base name, install per-user via `AddFontResourceW` +
   `HKCU\...\Fonts` + `WM_FONTCHANGE`). Same font engine as before.
3. Build `<name>_para_illustrator.pdf` (`vectorizar_pdf.vectorizar_selectivo`): the VECTORIZE
   text is turned to curves **in place**, KEEP text stays editable, and **images/graphics are
   left untouched** (never rasterized). If nothing needs vectorizing, the original is used as-is.
4. Open that output in Illustrator.

Net result: body text editable with the right fonts, math/symbols as faithful vectors, images
intact, output ≈ same size as the original. Verified by rendering original vs output
page-by-page (remaining diffs are anti-aliasing only, well under ~4%).

Everything downloaded/installed lives under one deletable folder,
`%LOCALAPPDATA%\ArreglarPDF-Illustrator` (`fuentes.APP_DIR`), tracked in
`fuentes_instaladas.json`. The `_para_illustrator.pdf` copies sit next to each source PDF and
are safe to delete (regenerated on demand).

## How the selective vectorization works (the delicate part)

`vectorizar_selectivo(pdf, vector_bases)` rebuilds the doc page-by-page:
- `_analiza` reads every text span once → VECTORIZE char-rects + span-rects, KEEP span-rects,
  and a total-glyph count.
- `_vector_aislado` builds a **text-only** vector of the page: on a copy, redact the KEEP text,
  then redact **all images and line-art** (a full-page redaction, `images=REMOVE,
  graphics=REMOVE, text=NONE`), then `get_svg_image(text_as_path=True)` → PDF. Stripping images
  here is what prevents **black boxes**: PyMuPDF's SVG export renders alpha/SMask images as solid
  black, so images must never go through SVG — they stay in the original page instead.
- Output page: redact the VECTORIZE text (keeping images/graphics), then `show_pdf_page` the
  text-only vector on top.
- Redaction granularity: **per-span** when ≥90% of a page's glyphs are VECTORIZE (fast — Office/
  PowerPoint slides), **per-char** on mixed pages (tight — protects body text next to inline
  math). Per-char on an all-vector page was the original multi-minute slowdown.
- Rotated pages are left untouched (the overlay wouldn't align); use `--vector` if one ever needs it.

## Files

- `fuentes.py` — font engine. `escanear()`, `clasificar()` (name→family/size/style),
  `asegurar_familia()` (download+cache+extract), `elegir_otf()`, `renombrar_otf()`,
  `instalar_fuente()`/`desinstalar_todo()`. **`es_vectorizable(fo, editable)`** is the
  KEEP/VECTORIZE decision; **`plan_hibrido(pdf, editable, dry)`** scans, installs the KEEP
  families, and returns the set of bases to vectorize. `provision()` (the older
  install-everything path, incl. math→LM-Math) is kept but is no longer the default. CLI:
  `--dry`, `--editable`, `--borrar`.
- `vectorizar_pdf.py` — **`vectorizar_selectivo(pdf, vector_bases)`** (default engine; helpers
  `_analiza`, `_vector_aislado`, `_annot`, `_apply`, and the `PDF_REDACT_*` constants). Also the
  older full-document outliner `vectorizar_a_pdf()` (one `_curvas.pdf`, used by `--vector`) and
  `vectorizar_a_svg()` (`--svg`, per-page).
- `arreglar_y_abrir.py` — orchestrator for the right-click menu: `flujo_hibrido` (default) and
  `flujo_vector` (`--vector`). Flags: `--no-open`, `--editable`, `--vector`, `--solo-fuentes`.
- `diagnostico_fuentes.py` — font detection/report. Other modules import helpers from here
  (`fuentes.py`→`is_installed`) — keep `is_installed`/`fuentes_riesgo`/`norm`/`installed_fonts`
  importable.
- `INSTALAR.ps1`/`.bat` — register the HKCU right-click menu for `.pdf` and ensure `pymupdf` +
  `fonttools`. `DESINSTALAR.ps1` removes the menu **and** the fonts. `BORRAR_FUENTES.bat` →
  `fuentes.py --borrar`.
- `abrir_illustrator.bat` — launcher the menu points at (`py arreglar_y_abrir.py "%1"`).

## Requirements

**Python 3** (launchers call `py`; `python` also works) with **`pymupdf`** (imported as
`pymupdf`, falling back to legacy `fitz`) and **`fontTools`**; `INSTALAR.ps1` pip-installs both
if missing. No admin anywhere; Windows-only (`ctypes`/`winreg`). `numpy`/`PIL` are only used by
throwaway verification scripts, not by the tool itself.

## Commands

```powershell
# See the KEEP-vs-VECTORIZE decision for a PDF (no changes made):
python fuentes.py --dry "ruta\al.pdf"

# Full fix (install KEEP fonts + build <name>_para_illustrator.pdf) without launching AI:
python arreglar_y_abrir.py "ruta\al.pdf" --no-open

# Keep already-installed system fonts editable too (less vectorizing, trusts Illustrator):
python arreglar_y_abrir.py "ruta\al.pdf" --editable --no-open

# Ultimate fallback: pass ALL text to curves (nothing editable):
python arreglar_y_abrir.py "ruta\al.pdf" --vector --no-open

# Remove everything this tool installed/downloaded:
python fuentes.py --borrar
```

No test suite. Validate by rendering the original vs `_para_illustrator.pdf` page-by-page
(PyMuPDF `get_pixmap` + a numpy pixel diff) — differences should be anti-aliasing only; a page
jumping to tens-of-% means something is wrong (e.g. black boxes → an image leaked into the SVG,
or missing content). Good real PDFs in `Downloads`: `Pr3-SistemasEcuaciones.pdf`,
`Modelo_Física_Madrid_2025.pdf` (LaTeX); `Simulacro Examen Mates CCSS.pdf` (Word+CambriaMath);
and `UD 4-Distribuciones discretas_2026_def.pdf` (PowerPoint, under `OneDrive\Documents\SEGUNDO
CURSO\EST`). To confirm an installed KEEP font is visible to Illustrator, enumerate GDI families
via `ctypes` `EnumFontFamiliesExW`.

## Gotchas

- **Illustrator must be fully closed** before opening, or it won't see fonts installed after it
  started. The orchestrator warns when it detects a running instance (only matters when KEEP
  fonts were just installed).
- **Math/symbols are vectorized by default now, not substituted.** The old path installed Latin
  Modern Math renamed to `CMMI10`/etc., but the PDF's Type1 subset encoding + CM glyph names
  don't line up with a Unicode math OTF, so symbols garbled. Outlining those glyphs is exact and
  Illustrator-independent. (`provision()`'s math-install path still exists but isn't used by the
  default flow.)
- **Never send images through `get_svg_image`.** PyMuPDF renders alpha/SMask images as solid
  black boxes. `_vector_aislado` strips all images/line-art before the SVG step and the originals
  stay on the page. A regression here shows as black rectangles behind text on Office/PowerPoint
  pages — the single most important invariant in `vectorizar_pdf.py`.
- `es_vectorizable` precedence: `Type3`→vector, `Type0`/CID→vector, `clasificar()` math→vector,
  `clasificar()` text-family→KEEP, else (unknown) → vector unless `--editable` and already
  installed. So plain Office PDFs (Calibri/Arial/Aptos) get **fully vectorized** by default
  (guaranteed identical, not editable); LaTeX PDFs keep body text editable and vectorize only
  the math. `--editable` keeps installed system fonts as text (more editable, trusts Illustrator).
- `clasificar()` size parsing: plain CM names use the number as points (`CMR10`→10pt); CM-super
  `SF*` and any trailing number ≥100 are treated as points×100 (`SFRM1200`→12pt, `SFBX1728`
  →17pt). Snapped to the nearest Latin Modern optical master.
- `is_installed()` tests against `diagnostico_fuentes.INSTALLED`, a snapshot of the font
  **registry** (HKLM+HKCU) read **once at import** — it won't see fonts installed later in the
  same process (fine: scan happens before install), and it matches by loose substring so it can
  disagree with what GDI/Illustrator actually resolve.
- Provisioning is **idempotent** (a base already in the manifest with its file present is
  skipped). Font downloads: the three GUST zips (`lm`, `lmmath`, `texgyre`) self-heal via
  `_resolver_url()` (HEAD-check the pinned URL, else scrape the page for the current
  `*otf*.zip`); **STIX** pulls individual `.otf` from GitHub `raw` on `master` with no fallback.
- The reassembled output preserves page geometry and the TOC (`set_toc`); internal links may not
  survive. Saved with `garbage=4, deflate=True` so it stays ≈ original size.
- Illustrator here is **2021** (pre-Type1-removal). Newer Illustrator drops Type1 entirely, which
  only makes outlining the symbols more necessary.
