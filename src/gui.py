# -*- coding: utf-8 -*-


import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from analyzer import analizar_texto  # noqa: E402


APP_TITLE = "Analizador de Compiscript — Léxico y Sintáctico"


class CompiscriptGUI(tb.Window):
    def __init__(self):
        super().__init__(themename="flatly")
        self.title(APP_TITLE)
        self.geometry("1180x720")
        self.minsize(900, 560)

        self.ruta_actual = None
        self.codigo_actual = ""

        self._construir_layout()

    # Construcción de la interfaz

    def _construir_layout(self):
        # --- Barra superior ---
        barra = tb.Frame(self, padding=12)
        barra.pack(side=TOP, fill=X)

        titulo = tb.Label(
            barra, text="Compiscript — Analizador Léxico y Sintáctico",
            font=("Segoe UI", 16, "bold")
        )
        titulo.pack(side=LEFT)

        self.btn_abrir = tb.Button(
            barra, text="📂 Seleccionar archivo .cps",
            bootstyle=PRIMARY, command=self.seleccionar_archivo
        )
        self.btn_abrir.pack(side=RIGHT, padx=(8, 0))

        self.btn_analizar = tb.Button(
            barra, text="▶ Analizar", bootstyle=SUCCESS,
            command=self.analizar, state=DISABLED
        )
        self.btn_analizar.pack(side=RIGHT, padx=(8, 0))

        self.lbl_archivo = tb.Label(
            self, text="Ningún archivo seleccionado.", padding=(12, 0),
            font=("Segoe UI", 10, "italic"), bootstyle=SECONDARY
        )
        self.lbl_archivo.pack(side=TOP, fill=X)

        # BODY
        cuerpo = tb.Panedwindow(self, orient=HORIZONTAL)
        cuerpo.pack(fill=BOTH, expand=YES, padx=12, pady=12)

        # Panel izquierdo
        panel_codigo = tb.Frame(cuerpo, padding=4)
        tb.Label(
            panel_codigo, text="Código fuente", font=("Segoe UI", 11, "bold")
        ).pack(side=TOP, anchor=W, pady=(0, 4))

        frame_txt = tb.Frame(panel_codigo)
        frame_txt.pack(fill=BOTH, expand=YES)

        self.num_lineas = tk.Text(
            frame_txt, width=5, padx=4, takefocus=0, border=0,
            background="#eef1f5", foreground="#7a8794", state=DISABLED,
            font=("Consolas", 10)
        )
        self.num_lineas.pack(side=LEFT, fill=Y)

        self.txt_codigo = tk.Text(
            frame_txt, wrap="none", undo=True, font=("Consolas", 10),
            background="#ffffff", foreground="#212529"
        )
        self.txt_codigo.pack(side=LEFT, fill=BOTH, expand=YES)
        self.txt_codigo.bind("<<Modified>>", self._on_codigo_modificado)

        scroll_y = tb.Scrollbar(frame_txt, orient=VERTICAL, command=self._scroll_ambos)
        scroll_y.pack(side=RIGHT, fill=Y)
        self.txt_codigo.configure(yscrollcommand=self._on_yscroll)

        # Resaltado de línea con error
        self.txt_codigo.tag_configure("linea_error", background="#fde2e1")

        cuerpo.add(panel_codigo, weight=1)

        # Panel derecho
        panel_resultados = tb.Frame(cuerpo, padding=4)

        cab_resultados = tb.Frame(panel_resultados)
        cab_resultados.pack(side=TOP, fill=X, pady=(0, 4))
        tb.Label(
            cab_resultados, text="Resultados del análisis",
            font=("Segoe UI", 11, "bold")
        ).pack(side=LEFT)

        self.lbl_resumen = tb.Label(
            cab_resultados, text="", font=("Segoe UI", 10, "bold")
        )
        self.lbl_resumen.pack(side=RIGHT)

        # Filtro por tipo de error
        filtro_frame = tb.Frame(panel_resultados)
        filtro_frame.pack(side=TOP, fill=X, pady=(0, 6))
        tb.Label(filtro_frame, text="Mostrar:").pack(side=LEFT, padx=(0, 6))
        self.filtro_var = tk.StringVar(value="Todos")
        self.filtro_combo = tb.Combobox(
            filtro_frame, textvariable=self.filtro_var,
            values=["Todos", "Léxico", "Sintáctico"], state="readonly", width=14
        )
        self.filtro_combo.pack(side=LEFT)
        self.filtro_combo.bind("<<ComboboxSelected>>", lambda e: self._refrescar_tabla())

        # Tabla de errores
        columnas = ("tipo", "linea", "columna", "simbolo", "descripcion")
        self.tabla = tb.Treeview(
            panel_resultados, columns=columnas, show="headings",
            bootstyle=INFO, height=18
        )
        self.tabla.heading("tipo", text="Tipo")
        self.tabla.heading("linea", text="Línea")
        self.tabla.heading("columna", text="Columna")
        self.tabla.heading("simbolo", text="Símbolo / Lexema")
        self.tabla.heading("descripcion", text="Descripción")

        self.tabla.column("tipo", width=80, anchor=CENTER)
        self.tabla.column("linea", width=60, anchor=CENTER)
        self.tabla.column("columna", width=70, anchor=CENTER)
        self.tabla.column("simbolo", width=150, anchor=W)
        self.tabla.column("descripcion", width=420, anchor=W)

        self.tabla.tag_configure("Léxico", foreground="#b8860b")
        self.tabla.tag_configure("Sintáctico", foreground="#b02a37")

        scroll_tabla = tb.Scrollbar(panel_resultados, orient=VERTICAL, command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll_tabla.set)

        self.tabla.pack(side=LEFT, fill=BOTH, expand=YES)
        scroll_tabla.pack(side=RIGHT, fill=Y)

        self.tabla.bind("<<TreeviewSelect>>", self._on_seleccionar_error)

        cuerpo.add(panel_resultados, weight=1)

        #Barra de estado
        self.status = tb.Label(
            self, text="Listo.", padding=(12, 6), bootstyle=SECONDARY
        )
        self.status.pack(side=BOTTOM, fill=X)

        self._errores = []


    def _scroll_ambos(self, *args):
        self.txt_codigo.yview(*args)
        self.num_lineas.yview(*args)

    def _on_yscroll(self, first, last):
        self.num_lineas.yview_moveto(first)

    def _on_codigo_modificado(self, event=None):
        self.txt_codigo.edit_modified(False)

    def _actualizar_numeros_linea(self):
        contenido = self.txt_codigo.get("1.0", "end-1c")
        n = contenido.count("\n") + 1
        texto_numeros = "\n".join(str(i) for i in range(1, n + 1))
        self.num_lineas.configure(state=NORMAL)
        self.num_lineas.delete("1.0", "end")
        self.num_lineas.insert("1.0", texto_numeros)
        self.num_lineas.configure(state=DISABLED)


    def seleccionar_archivo(self):
        ruta = filedialog.askopenfilename(
            title="Selecciona un archivo Compiscript",
            filetypes=[("Archivos Compiscript", "*.cps"), ("Todos los archivos", "*.*")],
        )
        if not ruta:
            return
        try:
            with open(ruta, "r", encoding="utf-8", errors="replace") as f:
                codigo = f.read()
        except Exception as ex:
            messagebox.showerror("Error al abrir el archivo", str(ex))
            return

        self.ruta_actual = ruta
        self.codigo_actual = codigo
        self.txt_codigo.delete("1.0", "end")
        self.txt_codigo.insert("1.0", codigo)
        self._actualizar_numeros_linea()

        self.lbl_archivo.configure(text=f"Archivo: {ruta}")
        self.btn_analizar.configure(state=NORMAL)
        self._errores = []
        self._refrescar_tabla()
        self.lbl_resumen.configure(text="")
        self.status.configure(text="Archivo cargado. Presiona “Analizar” para comenzar.")

    def analizar(self):
        codigo = self.txt_codigo.get("1.0", "end-1c")
        self.status.configure(text="Analizando…")
        self.update_idletasks()

        try:
            resultado = analizar_texto(codigo, self.ruta_actual or "<sin nombre>")
        except Exception as ex:
            messagebox.showerror(
                "Error inesperado",
                f"Ocurrió un error inesperado durante el análisis:\n\n{ex}"
            )
            self.status.configure(text="Ocurrió un error inesperado.")
            return

        self._errores = resultado.errores
        self._refrescar_tabla()
        self._resaltar_lineas_con_error()

        n = len(self._errores)
        if n == 0:
            self.lbl_resumen.configure(
                text=" Sin errores", bootstyle=SUCCESS
            )
            self.status.configure(
                text="El archivo fue analizado correctamente. "
                     "No se encontraron errores léxicos ni sintácticos."
            )
        else:
            n_lex = len(resultado.errores_lexicos)
            n_sin = len(resultado.errores_sintacticos)
            self.lbl_resumen.configure(
                text=f" {n} error(es) — {n_lex} léxico(s), {n_sin} sintáctico(s)",
            )
            self.status.configure(
                text=f"Análisis finalizado: se encontraron {n} error(es)."
            )

    def _refrescar_tabla(self):
        for item in self.tabla.get_children():
            self.tabla.delete(item)

        filtro = self.filtro_var.get()
        for err in self._errores:
            if filtro != "Todos" and err.tipo != filtro:
                continue
            self.tabla.insert(
                "", "end",
                values=(err.tipo, err.linea, err.columna, err.simbolo, err.descripcion),
                tags=(err.tipo,)
            )

    def _resaltar_lineas_con_error(self):
        self.txt_codigo.tag_remove("linea_error", "1.0", "end")
        for err in self._errores:
            try:
                inicio = f"{err.linea}.0"
                fin = f"{err.linea}.end"
                self.txt_codigo.tag_add("linea_error", inicio, fin)
            except tk.TclError:
                pass

    def _on_seleccionar_error(self, event=None):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        valores = self.tabla.item(seleccion[0], "values")
        try:
            linea = int(valores[1])
        except (ValueError, IndexError):
            return
        self.txt_codigo.see(f"{linea}.0")
        self.txt_codigo.tag_remove("linea_actual", "1.0", "end")
        self.txt_codigo.tag_configure("linea_actual", background="#ffe08a")
        self.txt_codigo.tag_add("linea_actual", f"{linea}.0", f"{linea}.end")


def main():
    app = CompiscriptGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
