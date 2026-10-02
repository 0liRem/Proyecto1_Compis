# -*- coding: utf-8 -*-
"""
Registros de activación y direccionamiento en tiempo de ejecución.

Utilizando la tabla de simbolos

"""

from semantic.symbols import VariableSymbol, FunctionSymbol, ClassSymbol

WORD_SIZE = 4


class ActivationReport:
    #Hacel legible el TAC para verificación

    def __init__(self):
        self.globales = []     
        self.funciones = []    
        self.clases = []       
        self.tamano_datos_globales = 0

    def to_text(self):
        lineas = ["=== Área de datos globales ===",
                  f"(tamaño total: {self.tamano_datos_globales} bytes)"]
        for sym, offset in self.globales:
            lineas.append(f"  @{offset:<4} {sym.name}: {sym.type}")

        lineas.append("")
        lineas.append("=== Clases (layout de instancia) ===")
        for cls_sym, tam, campos in self.clases:
            lineas.append(f"  class {cls_sym.name}  (tamaño de instancia: {tam} bytes)")
            for nombre, offset, tipo in campos:
                lineas.append(f"    +{offset:<4} {nombre}: {tipo}")

        lineas.append("")
        lineas.append("=== Funciones / métodos (registros de activación) ===")
        for fsym, filas in self.funciones:
            lineas.append(
                f"  {fsym.tac_label}  (marco: {fsym.tac_frame_size} bytes, "
                f"retorno: {fsym.return_type})"
            )
            for nombre, categoria, offset, tipo in filas:
                lineas.append(f"    [{categoria:5}] +{offset:<4} {nombre}: {tipo}")
        return "\n".join(lineas)


def _flatten_variables(root_scope, usados, on_var):
    #Recorrer raiz para devolver cosas anidadas
    funciones_anidadas = []
    clases_anidadas = []

    def rec(scope):
        for nombre, sym in scope.symbols.items():
            if isinstance(sym, VariableSymbol):
                if getattr(sym, "tac_storage", None) is not None:
                    continue  # si ya esta asignado no hacer nada
                tac_nombre = nombre if nombre not in usados else f"{nombre}${id(sym) % 10000}"
                usados.add(tac_nombre)
                on_var(tac_nombre, sym)
            #Anidarlo
            elif isinstance(sym, FunctionSymbol):
                funciones_anidadas.append(sym)
            elif isinstance(sym, ClassSymbol):
                clases_anidadas.append(sym)
        for child in scope.children:
            if child.kind in ("block", "loop", "switch"):
                rec(child)

    rec(root_scope)
    return funciones_anidadas, clases_anidadas


def build_activation_records(checker) -> ActivationReport:
    symtab = checker.symtab
    reporte = ActivationReport()
    layouts_de_clase = {}  

    def procesar_clase(cls_sym):
        if id(cls_sym) in layouts_de_clase:
            return layouts_de_clase[id(cls_sym)]
        offset = 0
        campos = []
        if cls_sym.superclass is not None:
            offset, campos_base = procesar_clase(cls_sym.superclass)
            campos.extend(campos_base)
        for nombre, campo_sym in cls_sym.fields.items():
            campo_sym.tac_storage = "field"
            campo_sym.tac_offset = offset
            campo_sym.tac_name = nombre
            campos.append((nombre, offset, campo_sym.type))
            offset += WORD_SIZE
        cls_sym.tac_instance_size = offset
        layouts_de_clase[id(cls_sym)] = (offset, campos)
        reporte.clases.append((cls_sym, offset, list(campos)))

        metodos = list(cls_sym.methods.values())
        if cls_sym.constructor is not None and cls_sym.constructor not in metodos:
            metodos.append(cls_sym.constructor)
        for m in metodos:
            procesar_funcion(m, owner_class=cls_sym)
        return offset, campos

    def procesar_funcion(fsym, owner_class=None, prefijo_label=None):
        prefijo_label = prefijo_label or []
        if owner_class is not None:
            fsym.tac_label = f"{owner_class.name}_{fsym.name}"
        elif prefijo_label:
            fsym.tac_label = "__".join(prefijo_label + [fsym.name])
        else:
            fsym.tac_label = fsym.name

        filas = []
        usados = set()
        base_param = 0
        if owner_class is not None:
            filas.append(("this", "param", 0, owner_class.name))
            base_param = 1

        for idx, pname in enumerate(fsym.param_names):
            psym = fsym.scope.resolve_local(pname)
            offset = (base_param + idx) * WORD_SIZE
            psym.tac_storage = "param"
            psym.tac_offset = offset
            psym.tac_owner_function = fsym
            psym.tac_name = pname
            usados.add(pname)
            filas.append((pname, "param", offset, psym.type))

        frame_offset = [0]

        def on_local_var(tac_nombre, sym):
            offset = frame_offset[0]
            frame_offset[0] += WORD_SIZE
            sym.tac_storage = "local"
            sym.tac_offset = offset
            sym.tac_owner_function = fsym
            sym.tac_name = tac_nombre
            filas.append((tac_nombre, "local", offset, sym.type))

        funciones_anidadas, clases_anidadas = _flatten_variables(fsym.scope, usados, on_local_var)

        fsym.tac_locals_size = frame_offset[0]
        fsym.tac_param_area_size = (base_param + len(fsym.param_names)) * WORD_SIZE
        # tamaño provisional
        fsym.tac_frame_size = fsym.tac_param_area_size + fsym.tac_locals_size
        reporte.funciones.append((fsym, filas))

        for nf in funciones_anidadas:
            procesar_funcion(nf, prefijo_label=prefijo_label + [fsym.tac_label])
        for nc in clases_anidadas:
            procesar_clase(nc)

    # global
    global_offset = [0]
    usados_globales = set()

    def on_global_var(tac_nombre, sym):
        sym.tac_storage = "global"
        sym.tac_offset = global_offset[0]
        sym.tac_name = tac_nombre
        global_offset[0] += WORD_SIZE
        reporte.globales.append((sym, sym.tac_offset))

    funciones_top, clases_top = _flatten_variables(symtab.global_scope, usados_globales, on_global_var)
    reporte.tamano_datos_globales = global_offset[0]

    for f in funciones_top:
        procesar_funcion(f)
    for c in clases_top:
        procesar_clase(c)

    return reporte


def ampliar_marco_con_temporales(fsym, num_temporales: int):
    base = fsym.tac_frame_size
    fsym.tac_temp_area_size = num_temporales * WORD_SIZE
    fsym.tac_frame_size = base + fsym.tac_temp_area_size
    return base
