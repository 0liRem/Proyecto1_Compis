"""
    Parte Visual
    Creada con ayuda de ChatGPT
    Utiliza tkinter y ttk para toda la UI
    



"""

import os
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_GENERATED_DIR = os.path.join(_THIS_DIR, "generated")
for _p in (_THIS_DIR, _GENERATED_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from analyzer import analizar_texto  # noqa: E402
from CompiscriptParser import CompiscriptParser  # noqa: E402
from semantic.tree_view import export_tree_image  # noqa: E402
from semantic.symbols import VariableSymbol, FunctionSymbol, ClassSymbol  # noqa: E402

try:
    from PIL import Image, ImageTk  # noqa: E402
    _PIL_OK = True
except Exception:  # noqa: BLE001
    _PIL_OK = False


APP_TITLE = "Analizador de Compiscript — Léxico, Sintáctico y Semántico"


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
            barra, text="📂 Abrir .cps",
            bootstyle=PRIMARY, command=self.seleccionar_archivo
        )
        self.btn_abrir.pack(side=RIGHT, padx=(8, 0))

        self.btn_nuevo = tb.Button(
            barra, text="📄 Nuevo", bootstyle=SECONDARY, command=self.nuevo_archivo
        )
        self.btn_nuevo.pack(side=RIGHT, padx=(8, 0))

        self.btn_guardar = tb.Button(
            barra, text="💾 Guardar", bootstyle=SECONDARY, command=self.guardar_archivo
        )
        self.btn_guardar.pack(side=RIGHT, padx=(8, 0))

        self.btn_analizar = tb.Button(
            barra, text="▶ Analizar", bootstyle=SUCCESS,
            command=self.analizar, state=DISABLED
        )
        self.btn_analizar.pack(side=RIGHT, padx=(8, 0))

        self.btn_arbol = tb.Button(
            barra, text="🌳 Ver árbol sintáctico", bootstyle=INFO,
            command=self.mostrar_arbol, state=DISABLED
        )
        self.btn_arbol.pack(side=RIGHT, padx=(8, 0))

        self.btn_simbolos = tb.Button(
            barra, text="🔤 Tabla de símbolos", bootstyle=WARNING,
            command=self.mostrar_tabla_simbolos, state=DISABLED
        )
        self.btn_simbolos.pack(side=RIGHT, padx=(8, 0))

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
            values=["Todos", "Léxico", "Sintáctico", "Semántico"], state="readonly", width=14
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
        self.tabla.tag_configure("Semántico", foreground="#5a3d9e")

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


    def nuevo_archivo(self):
        self.ruta_actual = None
        self.codigo_actual = ""
        self.txt_codigo.delete("1.0", "end")
        self._actualizar_numeros_linea()
        self.lbl_archivo.configure(text="Archivo nuevo (sin guardar).")
        self.btn_analizar.configure(state=NORMAL)
        self.btn_arbol.configure(state=DISABLED)
        self.btn_simbolos.configure(state=DISABLED)
        self._errores = []
        self._resultado = None
        self._refrescar_tabla()
        self.lbl_resumen.configure(text="")
        self.status.configure(text="Nuevo archivo. Escribe tu código y presiona “Analizar”.")

    def guardar_archivo(self):
        ruta = self.ruta_actual
        if not ruta:
            ruta = filedialog.asksaveasfilename(
                title="Guardar archivo Compiscript",
                defaultextension=".cps",
                filetypes=[("Archivos Compiscript", "*.cps"), ("Todos los archivos", "*.*")],
            )
            if not ruta:
                return
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(self.txt_codigo.get("1.0", "end-1c"))
        except Exception as ex:
            messagebox.showerror("Error al guardar", str(ex))
            return
        self.ruta_actual = ruta
        self.lbl_archivo.configure(text=f"Archivo: {ruta}")
        self.status.configure(text="Archivo guardado.")

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
        self.btn_arbol.configure(state=DISABLED)
        self.btn_simbolos.configure(state=DISABLED)
        self._errores = []
        self._resultado = None
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
        self._resultado = resultado
        self.btn_arbol.configure(state=NORMAL if resultado.arbol is not None else DISABLED)
        self.btn_simbolos.configure(state=NORMAL if resultado.tabla_simbolos is not None else DISABLED)
        self._refrescar_tabla()
        self._resaltar_lineas_con_error()

        n = len(self._errores)
        if n == 0:
            self.lbl_resumen.configure(
                text=" Sin errores", bootstyle=SUCCESS
            )
            self.status.configure(
                text="El archivo fue analizado correctamente. "
                     "No se encontraron errores léxicos, sintácticos ni semánticos."
            )
        else:
            n_lex = len(resultado.errores_lexicos)
            n_sin = len(resultado.errores_sintacticos)
            n_sem = len(resultado.errores_semanticos)
            self.lbl_resumen.configure(
                text=f" {n} error(es) — {n_lex} léxico(s), {n_sin} sintáctico(s), "
                     f"{n_sem} semántico(s)",
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

    def mostrar_tabla_simbolos(self):
        """Muestra la tabla de símbolos y el historial de operaciones semánticas."""
        resultado = getattr(self, "_resultado", None)
        symtab = getattr(resultado, "tabla_simbolos", None) if resultado else None
        if symtab is None:
            messagebox.showinfo(
                "Tabla de símbolos no disponible",
                "Primero analiza un programa correctamente para construir la tabla."
            )
            return

        ventana = tk.Toplevel(self)
        ventana.title("Tabla de símbolos — inserción, recuperación, actualización y alcances")
        ventana.geometry("1180x700")
        ventana.minsize(900, 500)

        cab = tb.Frame(ventana, padding=12)
        cab.pack(fill=X)
        tb.Label(
            cab, text="Tabla de símbolos",
            font=("Segoe UI", 15, "bold")
        ).pack(side=LEFT)
        tb.Label(
            cab,
            text="  INSERTAR · RECUPERAR · ACTUALIZAR · ENTRAR/SALIR DE ALCANCE",
            bootstyle=SECONDARY,
            font=("Segoe UI", 9)
        ).pack(side=LEFT, padx=12)

        notebook = tb.Notebook(ventana)
        notebook.pack(fill=BOTH, expand=YES, padx=12, pady=(0, 12))

        # --- Símbolos por alcance ---
        tab_simbolos = tb.Frame(notebook, padding=8)
        notebook.add(tab_simbolos, text="  Símbolos por alcance  ")

        columnas = ("alcance", "nombre", "categoria", "tipo", "estado", "linea", "columna")
        tabla = tb.Treeview(tab_simbolos, columns=columnas, show="headings", bootstyle=INFO)
        encabezados = {
            "alcance": "Alcance",
            "nombre": "Nombre",
            "categoria": "Categoría",
            "tipo": "Tipo",
            "estado": "Estado",
            "linea": "Línea",
            "columna": "Columna",
        }
        anchos = {"alcance": 260, "nombre": 150, "categoria": 120, "tipo": 180,
                  "estado": 170, "linea": 60, "columna": 70}
        for col in columnas:
            tabla.heading(col, text=encabezados[col])
            tabla.column(col, width=anchos[col], anchor=CENTER if col in ("linea", "columna") else W)

        scroll = tb.Scrollbar(tab_simbolos, orient=VERTICAL, command=tabla.yview)
        tabla.configure(yscrollcommand=scroll.set)
        tabla.pack(side=LEFT, fill=BOTH, expand=YES)
        scroll.pack(side=RIGHT, fill=Y)

        def llenar_scope(scope, ruta=None):
            ruta = (ruta or []) + [scope.label or scope.kind]
            nombre_alcance = " / ".join(ruta)
            for sym in scope.symbols.values():
                if isinstance(sym, VariableSymbol):
                    categoria = "Constante" if sym.is_const else "Variable"
                    estado = "Inicializada" if sym.initialized else "No inicializada"
                elif isinstance(sym, FunctionSymbol):
                    categoria = "Función / método"
                    params = ", ".join(f"{n}: {t}" for n, t in zip(sym.param_names, sym.param_types))
                    estado = f"Parámetros: ({params})"
                elif isinstance(sym, ClassSymbol):
                    categoria = "Clase"
                    estado = f"Hereda de: {sym.superclass.name}" if sym.superclass else "Sin herencia"
                else:
                    categoria = type(sym).__name__
                    estado = "-"
                tabla.insert("", "end", values=(
                    nombre_alcance, sym.name, categoria,
                    str(sym.type) if sym.type is not None else "-",
                    estado, sym.line, sym.col
                ))
            for child in scope.children:
                llenar_scope(child, ruta)

        llenar_scope(symtab.global_scope)

        # --- Historial de operaciones ---
        tab_ops = tb.Frame(notebook, padding=8)
        notebook.add(tab_ops, text="  Operaciones realizadas  ")

        columnas_ops = ("operacion", "nombre", "tipo", "alcance", "resultado")
        tabla_ops = tb.Treeview(tab_ops, columns=columnas_ops, show="headings", bootstyle=WARNING)
        encabezados_ops = {
            "operacion": "Operación",
            "nombre": "Símbolo",
            "tipo": "Tipo",
            "alcance": "Alcance",
            "resultado": "Resultado / cambio",
        }
        for col in columnas_ops:
            tabla_ops.heading(col, text=encabezados_ops[col])
            tabla_ops.column(col, width={"operacion": 170, "nombre": 150, "tipo": 180,
                                         "alcance": 330, "resultado": 260}[col],
                             anchor=W)

        scroll_ops = tb.Scrollbar(tab_ops, orient=VERTICAL, command=tabla_ops.yview)
        tabla_ops.configure(yscrollcommand=scroll_ops.set)
        tabla_ops.pack(side=LEFT, fill=BOTH, expand=YES)
        scroll_ops.pack(side=RIGHT, fill=Y)

        for op in symtab.operation_log:
            tabla_ops.insert("", "end", values=(
                op["operation"], op["name"], op["type"], op["scope"], op["result"]
            ))

        pie = tb.Frame(ventana, padding=(12, 0, 12, 10))
        pie.pack(fill=X)
        tb.Label(
            pie,
            text="El alcance se lee de izquierda a derecha: global / función / bloque. "
                 "La recuperación busca primero en el alcance actual y luego en sus padres.",
            bootstyle=SECONDARY,
            wraplength=1000
        ).pack(side=LEFT)

    def mostrar_arbol(self):
        if not getattr(self, "_resultado", None) or self._resultado.arbol is None:
            messagebox.showinfo(
                "Árbol sintáctico no disponible",
                "No hay un árbol sintáctico para mostrar (el programa no "
                "pudo analizarse sintácticamente)."
            )
            return
        if not _PIL_OK:
            messagebox.showerror(
                "Falta una dependencia",
                "Se requiere el paquete 'Pillow' (PIL) para mostrar el "
                "árbol dentro de la aplicación. Instálalo con:\n\n"
                "    pip install Pillow"
            )
            return

        self.status.configure(text="Generando la representación visual del árbol…")
        self.update_idletasks()
        try:
            tmp_base = os.path.join(tempfile.gettempdir(), "compiscript_arbol")
            titulo = f"Árbol sintáctico — {os.path.basename(self.ruta_actual or '<sin nombre>')}"
            ruta_png = export_tree_image(
                self._resultado.arbol, CompiscriptParser, tmp_base, formato="png", titulo=titulo
            )
        except Exception as ex:
            messagebox.showerror(
                "No se pudo generar el árbol",
                f"Ocurrió un error generando la imagen del árbol (¿está "
                f"instalado Graphviz en el sistema?):\n\n{ex}"
            )
            self.status.configure(text="No se pudo generar el árbol.")
            return

        imagen = Image.open(ruta_png)
        ventana = tk.Toplevel(self)
        ventana.title("Árbol sintáctico")
        ventana.geometry("1000x700")

        contenedor = tb.Frame(ventana)
        contenedor.pack(fill=BOTH, expand=YES)

        canvas = tk.Canvas(contenedor, background="#ffffff")
        scroll_y = tb.Scrollbar(contenedor, orient=VERTICAL, command=canvas.yview)
        scroll_x = tb.Scrollbar(contenedor, orient=HORIZONTAL, command=canvas.xview)
        canvas.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.pack(side=RIGHT, fill=Y)
        scroll_x.pack(side=BOTTOM, fill=X)
        canvas.pack(side=LEFT, fill=BOTH, expand=YES)

        foto = ImageTk.PhotoImage(imagen)
        canvas.create_image(0, 0, anchor="nw", image=foto)
        canvas.image = foto  # evita que el garbage collector la elimine
        canvas.configure(scrollregion=(0, 0, imagen.width, imagen.height))

        self.status.configure(text="Árbol sintáctico generado.")

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
