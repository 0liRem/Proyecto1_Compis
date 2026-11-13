

from dataclasses import dataclass, field
from typing import Optional

from codegen.simulator import MipsSimulator, SimuladorError, formato_float


@dataclass
class Nodo:
    etiqueta: str
    args: list
    orden: int
    ret: Optional[str] = None
    devuelve: bool = False      # la función devuelve un valor 
    termino: bool = False       # llegó a retornar
    visible: bool = True        # False si quedó fuera por el límite de nodos
    cod_ret: Optional[str] = None
    hijos: list = field(default_factory=list)

    @property
    def texto(self):
        return f"{self.etiqueta}({', '.join(self.args)})"

    @property
    def resultado(self):
        if not self.devuelve:
            return None
        return self.ret if self.termino else "sin retornar"


@dataclass
class ArbolActivacion:
    raiz: Optional[Nodo]
    total: int                  # llamadas realizadas en toda la ejecución
    mostradas: int
    salida: str = ""
    error: Optional[str] = None

    @property
    def truncado(self):
        return self.mostradas < self.total

    def to_text(self):
        if self.raiz is None:
            return "(sin llamadas)"
        lineas = []

        def fila(n):
            r = n.resultado
            return n.texto + (f"  -> {r}" if r is not None else "")

        def rec(n, prefijo, ultimo, es_raiz=False):
            if es_raiz:
                lineas.append(fila(n))
                nuevo = ""
            else:
                lineas.append(prefijo + ("`-- " if ultimo else "|-- ") + fila(n))
                nuevo = prefijo + ("    " if ultimo else "|   ")
            for i, h in enumerate(n.hijos):
                rec(h, nuevo, i == len(n.hijos) - 1)

        rec(self.raiz, "", True, True)
        if self.truncado:
            lineas.append(f"... (se muestran {self.mostradas} de {self.total} llamadas)")
        if self.error:
            lineas.append(f"[la ejecución terminó con error: {self.error}]")
        return "\n".join(lineas)


class Trazador:
    def __init__(self, funciones, max_nodos=300):
        self.info = {f.asm: f for f in funciones}
        self.max_nodos = max_nodos
        self.pila = []
        self.raiz = None
        self.total = 0
        self.mostradas = 0

    # --- formato de valores ---
    @staticmethod
    def _cadena(sim, addr):
        if addr == 0:
            return "null"
        out = bytearray()
        try:
            while len(out) < 40:
                b, off = sim._region(addr & 0xFFFFFFFF, 1)
                if b[off] == 0:
                    break
                out.append(b[off])
                addr += 1
        except SimuladorError:
            return "?"
        txt = out.decode("utf-8", errors="replace")
        return '"' + (txt if len(out) < 40 else txt[:12] + "...") + '"'

    def _fmt(self, sim, valor, codigo):
        v = valor & 0xFFFFFFFF
        if codigo == "float":
            return formato_float(v)
        if codigo == "bool":
            return "true" if v else "false"
        if codigo == "string":
            return self._cadena(sim, v)
        if codigo == "ref":
            return "null" if v == 0 else "obj"
        return str(valor)

    # --- ganchos del simulador ---
    def llamar(self, sim, destino):
        info = self.info.get(destino)
        if info is None:                     # rutina del runtime: no es parte del árbol
            self.pila.append(None)
            return
        self.total += 1
        sp = sim.r[29]
        args = []
        for i, nombre in enumerate(info.params):
            cod = info.ptipos[i] if i < len(info.ptipos) else "int"
            if nombre == "this":
                args.append("this")
            else:
                args.append(f"{nombre.split('$')[0]}={self._fmt(sim, sim._lw(sp + 4 * i), cod)}")
        etiqueta = "main" if info.label == "__global__" else info.label
        nodo = Nodo(etiqueta, args, self.total, devuelve=info.ret is not None, cod_ret=info.ret)
        if self.raiz is None:
            self.raiz = nodo
            self.mostradas = 1
        else:
            padre = next((n for n in reversed(self.pila) if n is not None), None)
            if padre is not None and padre.visible and self.mostradas < self.max_nodos:
                padre.hijos.append(nodo)
                self.mostradas += 1
            else:
                nodo.visible = False
        self.pila.append(nodo)

    def retornar(self, sim):
        if not self.pila:
            return
        nodo = self.pila.pop()
        if nodo is not None:
            nodo.termino = True
            if nodo.devuelve:
                nodo.ret = self._fmt(sim, sim.r[2], nodo.cod_ret)


def trazar(programa, max_pasos=1_500_000, max_nodos=300):
    """Ejecuta `programa` (ProgramaMIPS) y devuelve su ArbolActivacion."""
    sim = MipsSimulator(programa.texto, max_pasos)
    tr = Trazador(programa.funciones, max_nodos)
    error = None
    try:
        sim.run(trace=tr)
    except SimuladorError as e:
        error = str(e)
    return ArbolActivacion(tr.raiz, tr.total, tr.mostradas, "".join(sim.out), error)


# ---------------------------------------------------------------------------
# Graphviz (mismo estilo que el árbol sintáctico)
# ---------------------------------------------------------------------------
def build_activation_graph(arbol, titulo="Árbol de activación"):
    import graphviz
    if arbol.truncado:
        titulo += f"  (se muestran {arbol.mostradas} de {arbol.total} llamadas)"
    g = graphviz.Digraph(name="arbol_activacion")
    g.attr(label=titulo, labelloc="t", fontsize="16", rankdir="TB", ordering="out")
    g.attr("node", fontname="Helvetica", fontsize="10")
    g.attr("edge", arrowsize="0.6", fontname="Helvetica", fontsize="8", fontcolor="#7a8794")
    if arbol.raiz is None:
        g.node("vacio", label="(sin llamadas)", shape="box")
        return g
    cont = {"n": 0}

    def visitar(n, es_raiz=False):
        cont["n"] += 1
        nid = f"n{cont['n']}"
        etiqueta = n.texto
        r = n.resultado
        if r is not None:
            etiqueta += f"\\n→ {r}"
        if es_raiz:
            g.node(nid, label=etiqueta, shape="ellipse", style="filled",
                   fillcolor="#d1f2e0", color="#2a9d5c")
        elif r == "sin retornar":
            g.node(nid, label=etiqueta, shape="ellipse", style="filled",
                   fillcolor="#f8d7da", color="#b02a37")
        else:
            g.node(nid, label=etiqueta, shape="ellipse", style="filled",
                   fillcolor="#d7e8fc", color="#2f6fb0")
        for h in n.hijos:
            hid = visitar(h)
            g.edge(nid, hid, label=str(h.orden))
        return nid

    visitar(arbol.raiz, es_raiz=True)
    return g


def export_activation_image(arbol, out_path_sin_extension, formato="png",
                            titulo="Árbol de activación"):
    g = build_activation_graph(arbol, titulo)
    return g.render(filename=out_path_sin_extension, format=formato, cleanup=True)
