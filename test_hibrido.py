"""Regresiones del modo hibrido; no instalan fuentes ni abren Illustrator."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf

import fuentes
import vectorizar_pdf as vec
import arreglar_y_abrir as app


class HibridoTests(unittest.TestCase):
    def crear_documento(self, ruta, rotacion=0):
        with pymupdf.open() as doc:
            page = doc.new_page(width=400, height=260)
            page.insert_text((40, 65), "Texto editable = 2", fontsize=18)
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), True)
            pix.clear_with(100)
            page.insert_image((50, 100, 170, 200), stream=pix.tobytes("png"))
            page.set_rotation(rotacion)
            doc.new_page(width=400, height=260).insert_text((40, 65), "Destino")
            doc[0].insert_link({"kind": pymupdf.LINK_GOTO,
                                "from": pymupdf.Rect(40, 40, 200, 80),
                                "page": 1, "to": pymupdf.Point(40, 65)})
            doc.set_metadata({"title": "Documento de prueba", "author": "Autor"})
            doc.set_toc([[1, "Destino", 2]])
            doc.save(ruta)

    def comprobar_render(self, antes, despues):
        self.assertEqual(antes.page_count, despues.page_count)
        for i in range(antes.page_count):
            a = antes[i].get_pixmap(matrix=pymupdf.Matrix(2, 2))
            b = despues[i].get_pixmap(matrix=pymupdf.Matrix(2, 2))
            self.assertEqual((a.width, a.height), (b.width, b.height))
            diferencia = sum(abs(x-y) for x, y in zip(a.samples, b.samples)) / (255 * len(a.samples))
            self.assertLess(diferencia, 0.0005)

    def test_paginas_rotadas(self):
        for rotacion in (90, 180, 270):
            with self.subTest(rotacion=rotacion), tempfile.TemporaryDirectory() as carpeta:
                path = Path(carpeta) / "rotado.pdf"
                self.crear_documento(path, rotacion)
                salida, cantidad = vec.vectorizar_selectivo(str(path), [])
                self.assertEqual(cantidad, 1)
                with pymupdf.open(path) as antes, pymupdf.open(salida) as despues:
                    self.assertEqual(despues[0].rotation, rotacion)
                    self.assertNotIn("=", despues[0].get_text())
                    self.assertIn("Texto editable", despues[0].get_text())
                    self.comprobar_render(antes, despues)

    def test_enlaces_y_metadatos(self):
        with tempfile.TemporaryDirectory() as carpeta:
            path = Path(carpeta) / "enlaces.pdf"
            self.crear_documento(path)
            salida, _ = vec.vectorizar_selectivo(str(path), [])
            with pymupdf.open(path) as antes, pymupdf.open(salida) as despues:
                self.assertEqual(len(despues[0].get_links()), 1)
                self.assertEqual(despues[0].get_links()[0]["page"], 1)
                self.assertEqual(despues.metadata["title"], antes.metadata["title"])
                self.assertEqual(despues.get_toc(), antes.get_toc())

    def test_vector_completo_con_transparencia(self):
        with tempfile.TemporaryDirectory() as carpeta:
            path = Path(carpeta) / "imagen.pdf"
            self.crear_documento(path)
            salida = vec.vectorizar_a_pdf(str(path))
            with pymupdf.open(path) as antes, pymupdf.open(salida) as despues:
                self.assertEqual(despues[0].get_text().strip(), "")
                self.assertEqual(len(despues[0].get_images()), len(antes[0].get_images()))
                self.comprobar_render(antes, despues)

    def test_error_no_sobrescribe_salida_anterior(self):
        with tempfile.TemporaryDirectory() as carpeta:
            path = Path(carpeta) / "original.pdf"
            out = Path(carpeta) / "salida.pdf"
            self.crear_documento(path)
            original = path.read_bytes()
            out.write_bytes(b"salida anterior")
            with patch.object(vec, "_vector_aislado", side_effect=RuntimeError("fallo simulado")):
                with self.assertRaisesRegex(RuntimeError, "pagina 1"):
                    vec.vectorizar_selectivo(str(path), [], out=str(out))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(out.read_bytes(), b"salida anterior")
            self.assertEqual(len(list(Path(carpeta).iterdir())), 2)
            with self.assertRaisesRegex(ValueError, "original"):
                vec.vectorizar_selectivo(str(path), [], out=str(path))

    def test_pagina_recortada(self):
        with tempfile.TemporaryDirectory() as carpeta:
            path = Path(carpeta) / "recortado.pdf"
            self.crear_documento(path)
            with pymupdf.open(path) as doc:
                doc[0].set_cropbox(pymupdf.Rect(20, 20, 380, 230))
                doc.saveIncr()
            salida, cantidad = vec.vectorizar_selectivo(str(path), [])
            self.assertEqual(cantidad, 1)
            with pymupdf.open(path) as antes, pymupdf.open(salida) as despues:
                self.assertEqual(antes[0].cropbox, despues[0].cropbox)
                self.comprobar_render(antes, despues)

    def test_dry_no_crea_carpetas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            with patch.object(fuentes, "FONTS_DIR", str(Path(carpeta) / "fuentes")), \
                    patch.object(fuentes, "CACHE_DIR", str(Path(carpeta) / "cache")), \
                    patch.object(fuentes, "escanear", return_value=[]), \
                    patch.object(fuentes, "_leer_manifest", return_value={}):
                fuentes.plan_hibrido("ejemplo.pdf", dry=True)
            self.assertEqual(list(Path(carpeta).iterdir()), [])

    def test_fuentes_texto_cid_y_simbolos(self):
        for base in ("ArialMT", "Calibri", "Aptos", "Cambria", "Arial-BoldMT"):
            with self.subTest(base=base):
                self.assertFalse(fuentes.es_vectorizable(
                    {"base": base, "tipo": "Type0", "instalada": True}))
        for base in ("SymbolMT", "CambriaMath", "Wingdings", "CMSY10", "STIXMath"):
            with self.subTest(base=base):
                self.assertTrue(fuentes.es_vectorizable(
                    {"base": base, "tipo": "Type0", "instalada": True}))
        self.assertTrue(fuentes.es_vectorizable(
            {"base": "Desconocida", "tipo": "Type0", "instalada": False}))
        self.assertTrue(fuentes.es_vectorizable(
            {"base": "Arial", "tipo": "Type3", "instalada": True}))

    def test_solo_fuentes_no_crea_pdf(self):
        plan = {"keep_sistema": [], "instaladas": [], "ya": [], "vector": []}
        with patch.object(fuentes, "plan_hibrido", return_value=plan), \
                patch.object(vec, "vectorizar_selectivo") as convertir:
            app.flujo_hibrido("ejemplo.pdf", True, True, False)
        convertir.assert_not_called()

    def test_texto_y_simbolos_en_la_misma_fuente(self):
        fuente = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arial.ttf"
        if not fuente.exists():
            self.skipTest("Requiere Arial de Windows")
        with tempfile.TemporaryDirectory() as carpeta:
            original = Path(carpeta) / "original.pdf"
            with pymupdf.open() as doc:
                page = doc.new_page(width=500, height=240)
                page.insert_font(fontname="Arial", fontfile=str(fuente))
                page.insert_text((30, 65), "Texto editable: parámetro θ, μ, σ y p.",
                                 fontname="Arial", fontsize=18)
                page.insert_text((30, 110), "Texto normal sin simbolos.",
                                 fontname="Arial", fontsize=18)
                page.draw_rect((25, 140, 200, 190), color=(0, 0, 1), fill=(0.8, 0.9, 1))
                # Imagen semitransparente: no debe entrar en la conversion SVG.
                pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 16, 16), True)
                pix.clear_with(120)
                page.insert_image((240, 140, 300, 200), stream=pix.tobytes("png"))
                doc.save(original)
            salida, cantidad = vec.vectorizar_selectivo(str(original), [])
            self.assertEqual(cantidad, 3)
            with pymupdf.open(original) as antes, pymupdf.open(salida) as despues:
                texto = despues[0].get_text().replace("\xa0", " ")
                self.assertIn("Texto editable: parámetro", texto)
                self.assertIn("y p.", texto)
                self.assertIn("Texto normal sin simbolos.", texto)
                for simbolo in "θμσ":
                    self.assertNotIn(simbolo, texto)
                def caracteres(page):
                    return [c for bloque in page.get_text("rawdict")["blocks"]
                            for linea in bloque.get("lines", [])
                            for span in linea["spans"] for c in span["chars"]
                            if not c["c"].isspace() and c["c"] not in "θμσ"]
                originales = caracteres(antes[0])
                conservados = caracteres(despues[0])
                self.assertEqual(len(originales), len(conservados))
                for a, b in zip(originales, conservados):
                    self.assertEqual(a["c"], b["c"])
                    self.assertAlmostEqual(a["origin"][0], b["origin"][0], delta=0.02)
                    self.assertAlmostEqual(a["origin"][1], b["origin"][1], delta=0.02)
                self.assertEqual(len(antes[0].get_images()), len(despues[0].get_images()))
                self.assertTrue(despues[0].get_drawings())
                a = antes[0].get_pixmap(matrix=pymupdf.Matrix(2, 2)).samples
                b = despues[0].get_pixmap(matrix=pymupdf.Matrix(2, 2)).samples
                diferencia = sum(abs(x - y) for x, y in zip(a, b)) / (255 * len(a))
                self.assertLess(diferencia, 0.0005, "El render ha cambiado demasiado")
                print("Diferencia media normalizada del render: %.6f" % diferencia)


if __name__ == "__main__":
    unittest.main()
