# -*- coding: utf-8 -*-
"""
Optimización por mirilla


Transformaciones
  R1  Salto al siguiente      `j L` / `beqz r, L` justo antes de `L:`  -> se elimina
  R2  Identidades             `move r,r`, `addiu r,r,0`, `sll r,r,0`   -> se elimina
                              `addiu a,b,0`, `addu a,b,$zero`          -> `move a,b`
  R3  Carga tras almacenam.   `sw r,A` + `lw q,A`                      -> `move q,r`
  R4  Código inalcanzable     instrucciones entre `j`/`jr` y la sig. etiqueta
  R5  Reducción de fuerza     `mul d,a,2^k` -> `sll d,a,k`; `*1` -> move; `*0` -> li 0
  R6  Plegado de constantes   `li a,c1; li b,c2; addu d,a,b`           -> `li d,c1+c2`
  R7  Operando inmediato      `li b,c; addu d,a,b`                     -> `addiu d,a,c`
  R8  Encadenamiento de saltos`j L1` con `L1: j L2`                    -> `j L2`
  R9  Valor muerto            instrucción cuyo resultado no se vuelve a leer
                              (análisis de vida de registros $t sobre el flujo de control)
"""

import re
from dataclasses import dataclass, field

NOMBRES_REGLAS = {
    "R1": "Salto al siguiente",
    "R2": "Identidades algebraicas",
    "R3": "Carga tras almacenamiento",
    "R4": "Código inalcanzable",
    "R5": "Reducción de fuerza",
    "R6": "Plegado de constantes",
    "R7": "Operando inmediato",
    "R8": "Encadenamiento de saltos",
    "R9": "Valor muerto (liveness)",
}

_RE_LABEL = re.compile(r"^([A-Za-z_.$][\w.$]*):\s*(#.*)?$")
_RE_MEM = re.compile(r"^(-?\d+)?\((\$\w+)\)$")
_BRANCH2 = {"beqz", "bnez"}
_BRANCH3 = {"beq", "bne"}
_ARIT3 = {"addu", "add", "subu", "sub", "mul", "slt", "sltu"}
_ARITI = {"addiu", "addi", "sll", "xori", "sltiu", "andi", "ori"}
_FLOAT3 = {"add.s", "sub.s", "mul.s", "div.s"}
_BORRABLES_MEM = {"$fp", "$sp", "$s7"}
_TEMPS = {f"$t{i}" for i in range(10)}
CONOCIDAS = ({"li", "la", "move", "lw", "sw", "lb", "sb", "div", "mflo", "mfhi", "j", "jal", "jr",
              "syscall", "mtc1", "mfc1", "neg.s", "cvt.s.w", "c.lt.s", "c.le.s", "c.eq.s",
              "bc1t", "bc1f", "nop"}
             | _BRANCH2 | _BRANCH3 | _ARIT3 | _ARITI | _FLOAT3)
_TODOS = {f"$t{i}" for i in range(10)} | {f"$s{i}" for i in range(8)} | {
    "$v0", "$v1", "$a0", "$a1", "$a2", "$a3", "$ra", "$fp", "$sp", "$f12", "FCC"}
_HELPERS = ("__str_concat", "__str_eq", "__print_bool", "__print_str", "__rt_")


@dataclass
class Item:
    kind: str                 # 'ins' | 'label' | 'comment' | 'other'
    text: str
    mn: str = ""
    ops: list = field(default_factory=list)
    label: str = ""


@dataclass
class ResultadoOptimizacion:
    texto: str
    antes: int
    despues: int
    reglas: dict

    @property
    def eliminadas(self):
        return self.antes - self.despues

    def resumen(self):
        det = ", ".join(f"{k}={v}" for k, v in sorted(self.reglas.items()) if v)
        return (f"Optimizacion por mirilla: {self.antes} -> {self.despues} instrucciones"
                f" ({self.eliminadas} menos)" + (f"  [{det}]" if det else ""))


def _parse_linea(ln):
    s = ln.strip()
    if not s:
        return Item("other", ln)
    if s.startswith("#"):
        return Item("comment", ln)
    m = _RE_LABEL.match(s)
    if m:
        return Item("label", ln, label=m.group(1))
    if s.startswith("."):
        return Item("other", ln)
    s = s.split("#")[0].strip()
    mn, _, ops = s.partition(" ")
    ops = [o.strip() for o in ops.split(",")] if ops.strip() else []
    return Item("ins", ln, mn=mn, ops=ops)


def _fmt(mn, *ops):
    return f"    {mn} " + ", ".join(ops) if ops else f"    {mn}"


# ---------------------------------------------------------------------------
# Usos y definiciones de registros (para el análisis de vida)
# ---------------------------------------------------------------------------
def _es_reg(o):
    return o.startswith("$")


def usos_defs(it):
    mn, o = it.mn, it.ops
    u, d = set(), set()

    def uso(x):
        if _es_reg(x):
            u.add(x)

    def mem(x):
        m = _RE_MEM.match(x)
        if m:
            u.add(m.group(2))

    if mn in ("li", "la"):
        d.add(o[0])
    elif mn == "move":
        d.add(o[0]); uso(o[1])
    elif mn in ("lw", "lb"):
        d.add(o[0]); mem(o[1])
    elif mn in ("sw", "sb"):
        uso(o[0]); mem(o[1])
    elif mn in _ARIT3:
        d.add(o[0]); uso(o[1]); uso(o[2])
    elif mn in _ARITI:
        d.add(o[0]); uso(o[1])
    elif mn == "div":
        uso(o[0]); uso(o[1])
    elif mn in ("mflo", "mfhi"):
        d.add(o[0])
    elif mn in _BRANCH2:
        uso(o[0])
    elif mn in _BRANCH3:
        uso(o[0]); uso(o[1])
    elif mn == "jr":
        uso(o[0]); u.add("$v0")
    elif mn == "mtc1":
        uso(o[0]); d.add(o[1])
    elif mn == "mfc1":
        d.add(o[0]); uso(o[1])
    elif mn in _FLOAT3:
        d.add(o[0]); uso(o[1]); uso(o[2])
    elif mn in ("neg.s", "cvt.s.w"):
        d.add(o[0]); uso(o[1])
    elif mn in ("c.lt.s", "c.le.s", "c.eq.s"):
        uso(o[0]); uso(o[1]); d.add("FCC")
    elif mn in ("bc1t", "bc1f"):
        u.add("FCC")
    elif mn == "syscall":
        u.update({"$v0", "$a0", "$f12"}); d.add("$v0")
    elif mn not in CONOCIDAS:
        u.update(_TODOS)                       # desconocida: se asume que lee todo
    elif mn == "jal":
        if o[0].startswith(_HELPERS):          # las rutinas del runtime respetan $t0-$t7
            u.update({"$a0", "$a1"})
            d.update({"$v0", "$a0", "$a1", "$a2", "$a3", "$t8", "$t9"})
        else:                                  # función de usuario: $t/$v/$a son volátiles
            d.update(_TEMPS | {"$v0", "$v1", "$a0", "$a1", "$a2", "$a3"})
    return u, d


def _es_salto_incondicional(it):
    return it.kind == "ins" and (it.mn == "j" or (it.mn == "jr"))


def _destino(it):
    if it.mn == "j":
        return it.ops[0]
    if it.mn in _BRANCH2:
        return it.ops[1]
    if it.mn in _BRANCH3:
        return it.ops[2]
    if it.mn in ("bc1t", "bc1f"):
        return it.ops[0]
    return None


# ---------------------------------------------------------------------------
class Optimizador:
    def __init__(self, lineas, anotar=True):
        self.items = [_parse_linea(l) for l in lineas]
        self.anotar = anotar
        self.cuenta = {k: 0 for k in NOMBRES_REGLAS}

    # --- utilidades ---
    def _ins_idx(self):
        return [i for i, it in enumerate(self.items) if it.kind == "ins"]

    def _sig(self, i):
        """Índice de la siguiente instrucción (sin cruzar etiquetas) o None."""
        j = i + 1
        while j < len(self.items):
            k = self.items[j].kind
            if k == "ins":
                return j
            if k in ("label", "other"):
                return None
            j += 1
        return None

    def _ant(self, i):
        j = i - 1
        while j >= 0:
            k = self.items[j].kind
            if k == "ins":
                return j
            if k in ("label", "other"):
                return None
            j -= 1
        return None

    def _reemplazar(self, i, nuevo, regla):
        antes = self.items[i].text.strip()
        it = _parse_linea(nuevo)
        if self.anotar:
            it.text = f"{nuevo:<34}#~ {regla}: {antes}"
        self.items[i] = it
        self.cuenta[regla] += 1

    def _borrar(self, i, regla):
        antes = self.items[i].text.strip()
        self.items[i] = Item("comment", f"    #~ {regla} eliminada: {antes}" if self.anotar else None)
        self.cuenta[regla] += 1

    def _const(self, i, reg, ventana=4):
        """Valor entero de `reg` justo antes de la instrucción i si lo fijó un `li` cercano."""
        j, pasos = self._ant(i), 0
        while j is not None and pasos < ventana:
            it = self.items[j]
            if it.mn == "li" and it.ops[0] == reg:
                try:
                    return int(it.ops[1], 0)
                except ValueError:
                    return None
            _u, d = usos_defs(it)
            if reg in d or it.mn not in CONOCIDAS or it.mn == "syscall" or it.mn.startswith(("j", "b")):
                return None
            j = self._ant(j)
            pasos += 1
        return None

    # --- reglas de ventana ---
    def _pasada(self):
        cambio = False
        etiquetas = {}
        for i, it in enumerate(self.items):
            if it.kind == "label":
                etiquetas[it.label] = i
        n = len(self.items)
        for i in range(n):
            it = self.items[i]
            if it.kind != "ins":
                continue
            mn, o = it.mn, it.ops

            # R1: salto/bifurcación al destino inmediato
            dest = _destino(it)
            if dest is not None and mn in ({"j"} | _BRANCH2 | _BRANCH3):
                j = i + 1
                while j < n and self.items[j].kind in ("comment", "label"):
                    if self.items[j].kind == "label" and self.items[j].label == dest:
                        self._borrar(i, "R1"); cambio = True
                        break
                    j += 1
                if self.items[i].kind != "ins":
                    continue

            # R8: encadenamiento de saltos
            if dest is not None and mn in ({"j"} | _BRANCH2 | _BRANCH3) and dest in etiquetas:
                k = etiquetas[dest] + 1
                while k < n and self.items[k].kind in ("comment", "label"):
                    k += 1
                if k < n and self.items[k].kind == "ins" and self.items[k].mn == "j":
                    nuevo = self.items[k].ops[0]
                    if nuevo != dest and nuevo != (o[-1] if o else None):
                        ops = o[:-1] + [nuevo]
                        self._reemplazar(i, _fmt(mn, *ops), "R8"); cambio = True
                        continue

            # R2: identidades
            if mn == "move" and o[0] == o[1]:
                self._borrar(i, "R2"); cambio = True; continue
            if mn in ("addiu", "addi", "sll", "xori") and o[2] == "0":
                if o[0] == o[1]:
                    self._borrar(i, "R2")
                else:
                    self._reemplazar(i, _fmt("move", o[0], o[1]), "R2")
                cambio = True; continue
            if mn in ("addu", "add") and "$zero" in (o[1], o[2]):
                otro = o[2] if o[1] == "$zero" else o[1]
                if otro == o[0]:
                    self._borrar(i, "R2")
                else:
                    self._reemplazar(i, _fmt("move", o[0], otro), "R2")
                cambio = True; continue

            # R3: sw r,A ; lw q,A  -> move q,r
            if mn == "sw":
                j = self._sig(i)
                if j is not None and self.items[j].mn == "lw" and self.items[j].ops[1] == o[1]:
                    q = self.items[j].ops[0]
                    if q == o[0]:
                        self._borrar(j, "R3")
                    else:
                        self._reemplazar(j, _fmt("move", q, o[0]), "R3")
                    cambio = True
                    continue

            # R4: tras un salto incondicional no hay nada alcanzable hasta una etiqueta
            if mn in ("j", "jr"):
                j = self._sig(i)
                if j is not None:
                    while j is not None:
                        self._borrar(j, "R4")
                        cambio = True
                        j = self._sig(j)
                    continue

            if mn in _ARIT3:
                ca, cb = self._const(i, o[1]), self._const(i, o[2])

                # R6: plegado de constantes
                if ca is not None and cb is not None and mn in ("addu", "subu", "mul", "slt", "add", "sub"):
                    v = {"addu": ca + cb, "add": ca + cb, "subu": ca - cb, "sub": ca - cb,
                         "mul": ca * cb, "slt": int(ca < cb)}[mn]
                    v = ((v + 2 ** 31) % 2 ** 32) - 2 ** 31
                    self._reemplazar(i, _fmt("li", o[0], str(v)), "R6"); cambio = True; continue

                # R5: reducción de fuerza
                if mn == "mul" and (ca is not None or cb is not None):
                    c, otro = (cb, o[1]) if cb is not None else (ca, o[2])
                    if c == 0:
                        self._reemplazar(i, _fmt("li", o[0], "0"), "R5"); cambio = True; continue
                    if c == 1:
                        self._reemplazar(i, _fmt("move", o[0], otro), "R5"); cambio = True; continue
                    if c > 1 and c & (c - 1) == 0:
                        self._reemplazar(i, _fmt("sll", o[0], otro, str(c.bit_length() - 1)), "R5")
                        cambio = True; continue

                # R7: operando inmediato
                if mn in ("addu", "subu", "add", "sub"):
                    if cb is not None:
                        c = cb if mn in ("addu", "add") else -cb
                        if -32768 <= c <= 32767:
                            self._reemplazar(i, _fmt("addiu", o[0], o[1], str(c)), "R7")
                            cambio = True; continue
                    if ca is not None and mn in ("addu", "add") and -32768 <= ca <= 32767:
                        self._reemplazar(i, _fmt("addiu", o[0], o[2], str(ca)), "R7")
                        cambio = True; continue
        return cambio

    # --- R9: valores muertos con análisis de vida ---
    def _muertos(self):
        idx = self._ins_idx()
        if not idx:
            return False
        pos = {i: k for k, i in enumerate(idx)}
        ins = [self.items[i] for i in idx]
        n = len(ins)
        etiq = {}
        for i, it in enumerate(self.items):
            if it.kind == "label":
                etiq[it.label] = i
        # siguiente instrucción tras cada índice del texto (para resolver etiquetas)
        sig_de = [None] * (len(self.items) + 1)
        nxt = None
        for i in range(len(self.items) - 1, -1, -1):
            if self.items[i].kind == "ins":
                nxt = pos[i]
            sig_de[i] = nxt
        succ = []
        for k, it in enumerate(ins):
            s = []
            if it.mn == "j":
                t = etiq.get(it.ops[0])
                if t is not None and sig_de[t] is not None:
                    s.append(sig_de[t])
            elif it.mn == "jr":
                pass
            else:
                if k + 1 < n:
                    s.append(k + 1)
                dest = _destino(it)
                if dest is not None:
                    t = etiq.get(dest)
                    if t is not None and sig_de[t] is not None:
                        s.append(sig_de[t])
            succ.append(s)
        ud = [usos_defs(it) for it in ins]
        live_in = [set() for _ in range(n)]
        live_out = [set() for _ in range(n)]
        cambio = True
        while cambio:
            cambio = False
            for k in range(n - 1, -1, -1):
                out = set()
                for s in succ[k]:
                    out |= live_in[s]
                u, d = ud[k]
                nuevo_in = u | (out - d)
                if out != live_out[k] or nuevo_in != live_in[k]:
                    live_out[k], live_in[k] = out, nuevo_in
                    cambio = True
        hubo = False
        for k, it in enumerate(ins):
            if not self._sin_efectos(it):
                continue
            d = it.ops[0]
            if d in _TEMPS and d not in live_out[k]:
                self._borrar(idx[k], "R9")
                hubo = True
        return hubo

    @staticmethod
    def _sin_efectos(it):
        mn, o = it.mn, it.ops
        if mn in ("li", "la", "move", "mflo", "mfhi", "mfc1") or mn in _ARIT3 or mn in _ARITI:
            return True
        if mn == "lw":
            m = _RE_MEM.match(o[1])
            return m is None or m.group(2) in _BORRABLES_MEM
        return False

    def optimizar(self):
        for _ in range(20):
            c = False
            while self._pasada():
                c = True
            if self._muertos():
                c = True
            if not c:
                break
        return [it.text for it in self.items if it.text is not None]


def _contar(lineas):
    return sum(1 for ln in lineas
               if ln.startswith("    ") and not ln.strip().startswith("#") and ln.strip())


def optimizar_asm(texto, anotar=True):
    """Aplica la optimización por mirilla a la sección .text del ensamblador."""
    lineas = texto.split("\n")
    try:
        corte = next(i for i, l in enumerate(lineas) if l.strip() == ".data")
    except StopIteration:
        corte = len(lineas)
    cabeza, datos = lineas[:corte], lineas[corte:]
    antes = _contar(cabeza)
    opt = Optimizador(cabeza, anotar)
    nuevas = opt.optimizar()
    despues = _contar(nuevas)
    res = ResultadoOptimizacion("", antes, despues, dict(opt.cuenta))
    cab = [nuevas[0]] if nuevas else []
    resumen = "# " + res.resumen()
    cuerpo = nuevas[1:] if nuevas else []
    res.texto = "\n".join(cab + [resumen] + cuerpo + datos)
    return res
