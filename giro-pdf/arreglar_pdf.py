# -*- coding: utf-8 -*-
"""
Arreglar PDF para Illustrator
---------------------------------
Corrige los PDF que Illustrator abre GIRADOS.

Causa: muchos PDF (sobre todo "Imprimir a PDF" con Edge/Chrome desde
diapositivas horizontales) guardan la pagina en vertical + una etiqueta
/Rotate 90. Acrobat/Edge la respetan y se ve horizontal, pero Illustrator
IGNORA el /Rotate y lo abre girado.

Este programa "hornea" ese giro dentro del contenido: deja /Rotate = 0 y el
MediaBox ya en su orientacion real. Conserva los vectores (no rasteriza).

Uso:
  - Doble clic -> se abre la ventana -> arrastra el PDF dentro (o pulsa el boton).
  - Tambien puedes arrastrar uno o varios PDF directamente sobre "Arreglar PDF.bat".
"""

import os
import io
import sys
import traceback

# --- Logica de arreglo -------------------------------------------------------

def arreglar_pdf(path, reemplazar=False):
    """Devuelve (estado, ruta_salida, n_paginas, n_giradas).
    estado: 'arreglado' | 'ya_ok' | 'error'
    """
    from pypdf import PdfReader, PdfWriter

    # Leemos a memoria para poder sobrescribir el original con seguridad.
    with open(path, "rb") as fh:
        data = fh.read()
    reader = PdfReader(io.BytesIO(data))

    giradas = sum(1 for pg in reader.pages if ((pg.get("/Rotate") or 0) % 360) != 0)
    if giradas == 0:
        return ("ya_ok", path, len(reader.pages), 0)

    writer = PdfWriter()
    for pg in reader.pages:
        if ((pg.get("/Rotate") or 0) % 360) != 0:
            pg.transfer_rotation_to_content()  # hornea el giro en el contenido
        writer.add_page(pg)

    base, ext = os.path.splitext(path)
    if reemplazar:
        out = path
    else:
        if base.endswith("-FIXED"):
            out = base + ext          # no duplicar -FIXED-FIXED
        else:
            out = base + "-FIXED" + ext

    tmp = out + ".__tmp__"
    with open(tmp, "wb") as f:
        writer.write(f)
    os.replace(tmp, out)              # atomico (seguro aunque out == original)
    return ("arreglado", out, len(reader.pages), giradas)


# --- Interfaz grafica --------------------------------------------------------

import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import scrolledtext

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DND = True
except Exception:
    _DND = False


BG     = "#1e1f26"
CARD   = "#2a2c38"
ACCENT = "#4f8cff"
OKCOL  = "#39d98a"
WARN   = "#ffcc66"
ERRCOL = "#ff6b6b"
TXT    = "#e8e8ec"
MUTED  = "#9aa0b0"


class App:
    def __init__(self, root):
        self.root = root
        root.title("Arreglar PDF para Illustrator")
        root.configure(bg=BG)
        root.geometry("600x560")
        root.minsize(520, 480)

        self.reemplazar = tk.BooleanVar(value=False)

        # Cabecera
        tk.Label(root, text="Arreglar PDF para Illustrator", bg=BG, fg=TXT,
                 font=("Segoe UI Semibold", 17)).pack(pady=(18, 2))
        tk.Label(root, text="Corrige los PDF que Illustrator abre girados (vertical/horizontal).",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(pady=(0, 14))

        # Zona de arrastre
        self.drop = tk.Label(
            root,
            text=("\n\n⬇   Arrastra aquí tus PDF   ⬇\n\n"
                  + ("o pulsa el botón de abajo\n\n" if True else "")),
            bg=CARD, fg=TXT, font=("Segoe UI", 12),
            relief="ridge", bd=2, justify="center")
        self.drop.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        if _DND:
            self.drop.drop_target_register(DND_FILES)
            self.drop.dnd_bind("<<Drop>>", self.on_drop)
            self.drop.dnd_bind("<<DragEnter>>", lambda e: self.drop.config(bg="#34384a"))
            self.drop.dnd_bind("<<DragLeave>>", lambda e: self.drop.config(bg=CARD))
        else:
            self.drop.config(text="\n\nPulsa el botón para elegir tus PDF\n\n"
                                  "(arrastrar dentro no está disponible)\n")

        # Controles
        ctr = tk.Frame(root, bg=BG)
        ctr.pack(fill="x", padx=20)
        tk.Button(ctr, text="📂  Seleccionar PDF(s)", command=self.elegir,
                  bg=ACCENT, fg="white", activebackground="#3a6fd6",
                  activeforeground="white", relief="flat",
                  font=("Segoe UI Semibold", 11), padx=16, pady=8,
                  cursor="hand2").pack(side="left")
        tk.Checkbutton(ctr, text="Reemplazar el original (sin -FIXED)",
                       variable=self.reemplazar, bg=BG, fg=MUTED,
                       selectcolor=CARD, activebackground=BG,
                       activeforeground=TXT, font=("Segoe UI", 10)).pack(side="right")

        # Resultados
        self.log = scrolledtext.ScrolledText(
            root, height=8, bg="#15161c", fg=TXT, relief="flat",
            font=("Consolas", 9), padx=10, pady=8, wrap="word")
        self.log.pack(fill="both", expand=False, padx=20, pady=(12, 16))
        self.log.tag_config("ok",   foreground=OKCOL)
        self.log.tag_config("warn", foreground=WARN)
        self.log.tag_config("err",  foreground=ERRCOL)
        self.log.tag_config("muted", foreground=MUTED)
        self._write("Listo. Arrastra un PDF o selecciónalo para empezar.\n", "muted")
        self.log.config(state="disabled")

    # --- helpers UI ---
    def _write(self, text, tag=None):
        self.log.config(state="normal")
        self.log.insert("end", text, tag or "")
        self.log.see("end")
        self.log.config(state="disabled")
        self.root.update_idletasks()

    def elegir(self):
        paths = filedialog.askopenfilenames(
            title="Elige uno o varios PDF",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")])
        if paths:
            self.procesar(paths)

    def on_drop(self, event):
        self.drop.config(bg=CARD)
        paths = self.root.tk.splitlist(event.data)
        self.procesar(paths)

    # --- proceso ---
    def procesar(self, paths):
        pdfs = [p for p in paths if p.lower().endswith(".pdf")]
        no_pdf = [p for p in paths if not p.lower().endswith(".pdf")]
        if no_pdf:
            self._write("Ignorados (no son PDF): %d\n" % len(no_pdf), "muted")
        if not pdfs:
            self._write("No has soltado ningún PDF.\n", "warn")
            return

        arreglados = 0
        for p in pdfs:
            nombre = os.path.basename(p)
            try:
                estado, out, npag, ngir = arreglar_pdf(p, self.reemplazar.get())
                if estado == "arreglado":
                    arreglados += 1
                    self._write("✓ %s\n" % nombre, "ok")
                    self._write("   %d/%d páginas giradas corregidas  →  %s\n"
                                % (ngir, npag, os.path.basename(out)), "muted")
                elif estado == "ya_ok":
                    self._write("• %s — ya estaba correcto (sin rotación)\n" % nombre, "warn")
            except Exception as e:
                self._write("✗ %s — ERROR: %s\n" % (nombre, e), "err")
                self._write(traceback.format_exc() + "\n", "err")

        self._write("— Hecho. %d archivo(s) arreglado(s). —\n\n" % arreglados, "ok")


def main():
    args = [a for a in sys.argv[1:] if a.lower().endswith(".pdf")]
    root = TkinterDnD.Tk() if _DND else tk.Tk()
    app = App(root)
    if args:                       # arrastrados sobre el .bat
        root.after(300, lambda: app.procesar(args))
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Si algo peta antes de abrir la ventana, al menos mostrarlo.
        try:
            import tkinter.messagebox as mb
            mb.showerror("Error al iniciar", traceback.format_exc())
        except Exception:
            print(traceback.format_exc())
            input("Pulsa Enter para salir...")
