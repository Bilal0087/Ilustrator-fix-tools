# Repository Guidelines

## Project Structure & Module Organization

This Windows-only Python utility prepares PDFs for Adobe Illustrator. Source files live in the repository root:

- `arreglar_y_abrir.py`: orchestrates font provisioning, PDF conversion, and Illustrator launch.
- `fuentes.py`: classifies, downloads, and installs fonts per user.
- `vectorizar_pdf.py`: selective and full text outlining.
- `diagnostico_fuentes.py`: font inspection and shared detection helpers.
- `INSTALAR.ps1`, `DESINSTALAR.ps1`, and `.bat` launchers: Windows integration.

`CLAUDE.md` describes architecture and known pitfalls. `preview_pr3_p2.png` is a preview asset; `__pycache__/` is generated. There are no dedicated source, test, or asset directories.

## Build, Test, and Development Commands

Use Python 3 on Windows from the repository root:

```powershell
python -m pip install pymupdf fonttools
python -m compileall -q arreglar_y_abrir.py fuentes.py vectorizar_pdf.py diagnostico_fuentes.py
python fuentes.py --dry "path\sample.pdf"
python arreglar_y_abrir.py "path\sample.pdf" --no-open
```

These commands install dependencies, check Python syntax, inspect font decisions without changes, and prepare a PDF without launching Illustrator. The last command can install per-user fonts. Add `--vector` for full outlining or `--editable` to retain installed system fonts. There is no separate build step or local web server. `INSTALAR.ps1` installs the context menu and checks dependencies.

## Coding Style & Naming Conventions

Use four-space Python indentation, `snake_case` functions and variables, and uppercase constants. Follow surrounding code and keep new comments and user-facing messages in Spanish. Preserve importable diagnostic helpers. No formatter or linter configuration is present.

## Testing Guidelines

No automated framework or coverage threshold exists. Validate representative LaTeX and Office PDFs by rendering original and output pages with PyMuPDF and comparing them visually or through pixel differences. Check math glyphs, editable text, transparency, page geometry, and rotated pages. Never route images through the text-only SVG conversion: this can introduce black rectangles. Restart Illustrator after installing fonts before checking output there.

## Commit & Pull Request Guidelines

This checkout has no Git metadata, so commit conventions cannot be verified. Use concise imperative subjects. Describe behavior changes, validation commands, remaining limitations, and related issues in pull requests; include before/after page images for rendering changes.

## Agent Instructions

Work locally, install needed dependencies, and run applicable checks. Report what was verified and what could not be checked. Check interface changes locally where applicable. Do not push, merge into a deployment branch, or publish to production without explicit user authorization.