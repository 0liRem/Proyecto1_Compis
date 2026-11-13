# -*- coding: utf-8 -*-
"""

Convenciones

Registros
  $t0-$t7   valores de trabajo; los asigna getReg() (regalloc.py)
  $t8,$t9   scratch del generador y del runtime
  $s7       base del área de variables globales (__globals)
  $fp       base del marco de la función actual
  $sp       tope de la pila
  $v0       valor de retorno 
  $a0-$a3   argumentos de syscalls y de rutinas del runtime
  $f0,$f2   aritmética de punto flotante
"""

import re
import unicodedata
from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Optional

from semantic.types import INTEGER, FLOAT, BOOLEAN, STRING, VOID
from codegen.regalloc import RegisterAllocator, INF
from codegen import runtime

WORD = 4
_RE_TEMP = re.compile(r"^t(\d+)$")
_RE_INT = re.compile(r"^-?\d+$")
_RE_FLT = re.compile(r"^-?\d+\.\d+$")
BINOPS = {"+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">="}


class CodegenError(Exception):
    pass


def es_literal(x):
    return (x in ("null", "void") or _RE_INT.match(x) is not None
            or _RE_FLT.match(x) is not None or x.startswith('"'))


def _lecturas(ins):
    """Nombres/literales que la instrucción lee."""
    op, a = ins.op, ins.args
    if op in BINOPS or op in ("=", "uminus", "not", "itof", "array_len", "print",
                              "param", "return", "if_true", "if_false",
                              "array_new", "array_load", "array_store"):
        return [str(x) for x in a]
    if op == "field_load":
        return [a[0]]
    if op == "field_store":
        return [a[0], a[2]]
    if op == "noloc":
        return [a[0]]
    return []


@dataclass
class FuncInfo:
    label: str
    asm: str
    parent: Optional[str]
    params: list
    locals: list
    ntemps: int
    instrs: list
    slot: dict = field(default_factory=dict)
    ret: Optional[str] = None                     
    ptipos: list = field(default_factory=list)     

    @property
    def nslots(self):
        return len(self.locals) + self.ntemps

    @property
    def sl_off(self):      
        return 8 + WORD * len(self.params)


@dataclass
class ProgramaMIPS:
    texto: str
    estadisticas: dict
    funciones: list
    texto_original: str = ""     
    optimizacion: object = None    

    def to_text(self):
        return self.texto


def _codigo_tipo(t):
    if t is None:
        return "int"
    if t == FLOAT:
        return "float"
    if t == STRING:
        return "string"
    if t == BOOLEAN:
        return "bool"
    if t == INTEGER:
        return "int"
    return "ref"


def _asm_label(label):
    return label if label == "__global__" else "F_" + label


class _Emisor:
    def __init__(self, gen, fn):
        self.g = gen
        self.fn = fn
        self.lines = []
        self.pending = []
        self.pos = 0
        self._n = 0
        self._analizar()
        self.ra = RegisterAllocator(gen.pool, self._store, self._load, self._next_use)


    def out(self, s, indent=True):
        self.lines.append(("    " + s) if indent else s)

    def lbl(self, prefijo):
        self.g.nlabel += 1
        return f"__{prefijo}{self.g.nlabel}"

    @staticmethod
    def key(x):
        return "#" + x if es_literal(x) else x

    def _analizar(self):
        ins = self.fn.instrs
        n = len(ins)
        self.end = [n - 1] * n
        ini = 0
        for i, x in enumerate(ins):
            if x.op == "label" and i > ini:
                for j in range(ini, i):
                    self.end[j] = i - 1
                ini = i
            if x.op in ("goto", "if_true", "if_false", "return", "call"):
                for j in range(ini, i + 1):
                    self.end[j] = i
                ini = i + 1
        self.uses = {}
        for i, x in enumerate(ins):
            for nombre in _lecturas(x):
                self.uses.setdefault(nombre, []).append(i)

    def _next_use(self, clave):
        k = clave[1:] if clave.startswith("#") else clave
        lst = self.uses.get(k, [])
        j = bisect_right(lst, self.pos)
        if j < len(lst) and lst[j] <= self.end[self.pos]:
            return lst[j]
        return INF

    def _owner(self, nombre):
        """(FuncInfo dueña | None si global, desplazamiento)."""
        f = self.fn
        while f is not None:
            if nombre in f.slot:
                return f, -WORD * (f.slot[nombre] + 1)
            if nombre in f.params:
                return f, 8 + WORD * f.params.index(nombre)
            f = self.g.funcs.get(f.parent) if f.parent else None
        if nombre in self.g.globals:
            return None, self.g.globals[nombre]
        raise CodegenError(f"La variable '{nombre}' no tiene ubicación en '{self.fn.label}'.")

    def _addr(self, nombre, dueno=None):
        if dueno is None:
            dueno, off = self._owner(nombre)
        else:
            _, off = self._owner_en(dueno, nombre)
        if dueno is None:
            return f"{off}($s7)"
        if dueno is self.fn:
            return f"{off}($fp)"
        base = self._cadena_estatica("$t9", dueno)
        return f"{off}({base})"

    def _owner_en(self, f, nombre):
        if nombre in f.slot:
            return f, -WORD * (f.slot[nombre] + 1)
        if nombre in f.params:
            return f, 8 + WORD * f.params.index(nombre)
        raise CodegenError(f"'{nombre}' no pertenece a '{f.label}'.")

    def _cadena_estatica(self, reg, destino):
        """Deja en `reg` el $fp del marco de `destino` (ancestro léxico)."""
        cur, base = self.fn, "$fp"
        while cur is not destino:
            if cur.parent is None:
                raise CodegenError(f"'{destino.label}' no es ancestro de '{self.fn.label}'.")
            self.out(f"lw {reg}, {cur.sl_off}({base})")
            base = reg
            cur = self.g.funcs[cur.parent]
        return base


    def _load(self, clave, reg):
        if clave.startswith("#"):
            t = clave[1:]
            if t in ("null", "void"):
                self.out(f"li {reg}, 0")
            elif _RE_INT.match(t):
                self.out(f"li {reg}, {int(t)}")
            elif _RE_FLT.match(t):
                self.out(f"lw {reg}, {self.g.float_label(t)}")
            else:
                self.out(f"la {reg}, {self.g.string_label(t)}")
        else:
            self.out(f"lw {reg}, {self._addr(clave)}")

    def _store(self, nombre, reg):
        self.out(f"sw {reg}, {self._addr(nombre)}")

    def generar(self):
        fn, g = self.fn, self.g
        self.out(f"{fn.asm}:", indent=False)
        self.out(f"# --- prólogo: marco = {fn.nslots} ranuras locales/temporales + $ra/$fp ---")
        self.out("addiu $sp, $sp, -8")
        self.out("sw $ra, 4($sp)")
        self.out("sw $fp, 0($sp)")
        self.out("move $fp, $sp")
        if fn.nslots:
            self.out(f"addiu $sp, $sp, -{WORD * fn.nslots}")
        for nombre in fn.locals:      # las variables arrancan en 0
            self.out(f"sw $zero, {-WORD * (fn.slot[nombre] + 1)}($fp)")
        ins = fn.instrs
        for i, x in enumerate(ins):
            self.pos = i
            self._instr(i, x)
        self.ra.flush()
        self.out(f"__epi_{fn.label}:", indent=False)
        self.out("# --- epílogo ---")
        self.out("move $sp, $fp")
        self.out("lw $ra, 4($sp)")
        self.out("lw $fp, 0($sp)")
        self.out("addiu $sp, $sp, 8")
        self.out("jr $ra")
        for k, v in self.ra.stats.items():
            g.stats[k] = g.stats.get(k, 0) + v
        return self.lines

    def _instr(self, i, x):
        op = x.op
        if op == "label":
            self.ra.flush()
            self.out(f"{x.dest}:", indent=False)
            return
        if op == "comment":
            self.out(f"# {x.args[0]}")
            return
        self.out("# " + str(x).strip())
        nombre = "bin" if op in BINOPS else ("asig" if op == "=" else op)
        h = getattr(self, "_op_" + nombre, None)
        if h is None:
            raise CodegenError(f"Instrucción TAC sin traducción a MIPS: {op}")
        h(i, x)


    def _r(self, x, pinned):
        r = self.ra.get_reg(self.key(x), pinned)
        pinned.add(r)
        return r


    def _op_asig(self, i, x):
        r = self.ra.get_reg(self.key(x.args[0]), set())
        if self.key(x.dest) != self.key(x.args[0]):
            self.ra.alias(x.dest, r)

    def _op_goto(self, i, x):
        self.ra.flush()
        self.out(f"j {x.dest}")

    def _cond(self, x, instr):
        r = self.ra.get_reg(self.key(x.args[0]), set())
        self.ra.flush()
        self.out(f"{instr} {r}, {x.dest}")

    def _op_if_true(self, i, x):
        self._cond(x, "bnez")

    def _op_if_false(self, i, x):
        self._cond(x, "beqz")

    def _op_param(self, i, x):
        self.pending.append(x.args[0])

    def _op_call(self, i, x):
        label, n = x.args
        callee = self.g.funcs.get(label)
        if callee is None:
            raise CodegenError(f"Llamada a función desconocida '{label}'.")
        pend = self.pending[len(self.pending) - n:] if n else []
        del self.pending[len(self.pending) - n:]
        self.ra.flush()                       # la memoria queda al día
        extra = 1 if callee.parent else 0
        total = n + extra
        if total:
            self.out(f"addiu $sp, $sp, -{WORD * total}")
        for k, p in enumerate(pend):
            self._load(self.key(p), "$t8")
            self.out(f"sw $t8, {WORD * k}($sp)")
        if extra:
            padre = self.g.funcs[callee.parent]
            base = self._cadena_estatica("$t8", padre)
            if base != "$t8":
                self.out(f"move $t8, {base}")
            self.out(f"sw $t8, {WORD * n}($sp)")
        self.out(f"jal {callee.asm}")
        if total:
            self.out(f"addiu $sp, $sp, {WORD * total}")
        if x.dest is not None:
            r = self.ra.get_dest(set())
            self.out(f"move {r}, $v0")
            self.ra.define(x.dest, r)

    def _op_return(self, i, x):
        if x.args:
            r = self.ra.get_reg(self.key(x.args[0]), set())
            self.out(f"move $v0, {r}")
        self.ra.flush()
        sig = self.fn.instrs[i + 1] if i + 1 < len(self.fn.instrs) else None
        if sig is not None:
            self.out(f"j __epi_{self.fn.label}")

    def _op_print(self, i, x):
        r = self._r(x.args[0], set())
        t = x.tipo or "int"
        if t == "float":
            self.out(f"mtc1 {r}, $f12")
            self.out("li $v0, 2")
            self.out("syscall")
            self._nl()
        elif t == "bool":
            self.g.usa("print_bool")
            self.out(f"move $a0, {r}")
            self.out("jal __print_bool")
        elif t == "string":
            self.g.usa("print_str")
            self.out(f"move $a0, {r}")
            self.out("jal __print_str")
        else:
            self.out(f"move $a0, {r}")
            self.out("li $v0, 1")
            self.out("syscall")
            self._nl()

    def _nl(self):
        self.out("li $a0, 10")
        self.out("li $v0, 11")
        self.out("syscall")

    def _op_uminus(self, i, x):
        p = set()
        ra = self._r(x.args[0], p)
        rd = self.ra.get_dest(p)
        if x.tipo == "float":
            self.out(f"mtc1 {ra}, $f0")
            self.out("neg.s $f0, $f0")
            self.out(f"mfc1 {rd}, $f0")
        else:
            self.out(f"subu {rd}, $zero, {ra}")
        self.ra.define(x.dest, rd)

    def _op_not(self, i, x):
        p = set()
        ra = self._r(x.args[0], p)
        rd = self.ra.get_dest(p)
        self.out(f"xori {rd}, {ra}, 1")
        self.ra.define(x.dest, rd)

    def _op_itof(self, i, x):
        p = set()
        ra = self._r(x.args[0], p)
        rd = self.ra.get_dest(p)
        self.out(f"mtc1 {ra}, $f0")
        self.out("cvt.s.w $f0, $f0")
        self.out(f"mfc1 {rd}, $f0")
        self.ra.define(x.dest, rd)

    def _op_bin(self, i, x):
        op, t = x.op, (x.tipo or "int")
        p = set()
        ra = self._r(x.args[0], p)
        rb = self._r(x.args[1], p)
        rd = self.ra.get_dest(p)
        if t == "string":
            if op == "+":
                self.g.usa("str_concat")
                self.out(f"move $a0, {ra}")
                self.out(f"move $a1, {rb}")
                self.out("jal __str_concat")
                self.out(f"move {rd}, $v0")
            elif op in ("==", "!="):
                self.g.usa("str_eq")
                self.out(f"move $a0, {ra}")
                self.out(f"move $a1, {rb}")
                self.out("jal __str_eq")
                self.out(f"move {rd}, $v0")
                if op == "!=":
                    self.out(f"xori {rd}, {rd}, 1")
            else:
                raise CodegenError(f"Operador '{op}' no soportado para cadenas.")
        elif t == "float":
            self._float_bin(op, ra, rb, rd)
        else:
            self._int_bin(op, ra, rb, rd)
        self.ra.define(x.dest, rd)

    def _int_bin(self, op, ra, rb, rd):
        if op == "+":
            self.out(f"addu {rd}, {ra}, {rb}")
        elif op == "-":
            self.out(f"subu {rd}, {ra}, {rb}")
        elif op == "*":
            self.out(f"mul {rd}, {ra}, {rb}")
        elif op in ("/", "%"):
            self.g.usa("fatal")
            self.out(f"beqz {rb}, __rt_divzero")
            self.out(f"div {ra}, {rb}")
            self.out(f"{'mflo' if op == '/' else 'mfhi'} {rd}")
        elif op == "<":
            self.out(f"slt {rd}, {ra}, {rb}")
        elif op == ">":
            self.out(f"slt {rd}, {rb}, {ra}")
        elif op == "<=":
            self.out(f"slt {rd}, {rb}, {ra}")
            self.out(f"xori {rd}, {rd}, 1")
        elif op == ">=":
            self.out(f"slt {rd}, {ra}, {rb}")
            self.out(f"xori {rd}, {rd}, 1")
        elif op == "==":
            self.out(f"subu {rd}, {ra}, {rb}")
            self.out(f"sltiu {rd}, {rd}, 1")
        elif op == "!=":
            self.out(f"subu {rd}, {ra}, {rb}")
            self.out(f"sltu {rd}, $zero, {rd}")

    def _float_bin(self, op, ra, rb, rd):
        self.out(f"mtc1 {ra}, $f0")
        self.out(f"mtc1 {rb}, $f2")
        arit = {"+": "add.s", "-": "sub.s", "*": "mul.s", "/": "div.s"}
        if op in arit:
            self.out(f"{arit[op]} $f0, $f0, $f2")
            self.out(f"mfc1 {rd}, $f0")
            return
        cmp_ = {"<": ("c.lt.s $f0, $f2", False), "<=": ("c.le.s $f0, $f2", False),
                ">": ("c.lt.s $f2, $f0", False), ">=": ("c.le.s $f2, $f0", False),
                "==": ("c.eq.s $f0, $f2", False), "!=": ("c.eq.s $f0, $f2", True)}
        if op not in cmp_:
            raise CodegenError(f"Operador '{op}' no soportado para float.")
        ins, inv = cmp_[op]
        fin = self.lbl("fc")
        self.out(ins)
        self.out(f"li {rd}, {0 if inv else 1}")
        self.out(f"bc1t {fin}")
        self.out(f"li {rd}, {1 if inv else 0}")
        self.out(f"{fin}:", indent=False)

    def _op_array_new(self, i, x):
        n = str(x.args[0])
        p = set()
        if _RE_INT.match(n):
            self.out(f"li $a0, {WORD + WORD * int(n)}")
            rn = None
        else:
            rn = self._r(n, p)
            self.out(f"sll $a0, {rn}, 2")
            self.out("addiu $a0, $a0, 4")
        self.out("li $v0, 9")
        self.out("syscall")
        if rn is None:
            self.out(f"li $t8, {int(n)}")
            self.out("sw $t8, 0($v0)")
        else:
            self.out(f"sw {rn}, 0($v0)")
        rd = self.ra.get_dest(p)
        self.out(f"move {rd}, $v0")
        self.ra.define(x.dest, rd)

    def _elem_addr(self, ra, ri):
        self.g.usa("fatal")
        self.out(f"beqz {ra}, __rt_null")
        self.out(f"lw $t8, 0({ra})")
        self.out(f"sltu $t9, {ri}, $t8")
        self.out("beqz $t9, __rt_bounds")
        self.out(f"sll $t9, {ri}, 2")
        self.out(f"addu $t9, $t9, {ra}")

    def _op_array_load(self, i, x):
        p = set()
        ra = self._r(x.args[0], p)
        ri = self._r(x.args[1], p)
        rd = self.ra.get_dest(p)
        self._elem_addr(ra, ri)
        self.out(f"lw {rd}, 4($t9)")
        self.ra.define(x.dest, rd)

    def _op_array_store(self, i, x):
        p = set()
        ra = self._r(x.args[0], p)
        ri = self._r(x.args[1], p)
        rv = self._r(x.args[2], p)
        self._elem_addr(ra, ri)
        self.out(f"sw {rv}, 4($t9)")

    def _op_array_len(self, i, x):
        p = set()
        ra = self._r(x.args[0], p)
        rd = self.ra.get_dest(p)
        self.g.usa("fatal")
        self.out(f"beqz {ra}, __rt_null")
        self.out(f"lw {rd}, 0({ra})")
        self.ra.define(x.dest, rd)

    def _op_obj_new(self, i, x):
        tam = max(WORD, self.g.class_sizes.get(x.args[0], WORD))
        self.out(f"li $a0, {tam}")
        self.out("li $v0, 9")
        self.out("syscall")
        rd = self.ra.get_dest(set())
        self.out(f"move {rd}, $v0")
        self.ra.define(x.dest, rd)

    def _off(self, x):
        if x.extra is None:
            raise CodegenError(f"No se conoce el desplazamiento del atributo '{x.args[1]}'.")
        return x.extra

    def _op_field_load(self, i, x):
        p = set()
        ro = self._r(x.args[0], p)
        rd = self.ra.get_dest(p)
        self.g.usa("fatal")
        self.out(f"beqz {ro}, __rt_null")
        self.out(f"lw {rd}, {self._off(x)}({ro})")
        self.ra.define(x.dest, rd)

    def _op_field_store(self, i, x):
        p = set()
        ro = self._r(x.args[0], p)
        rv = self._r(x.args[2], p)
        self.g.usa("fatal")
        self.out(f"beqz {ro}, __rt_null")
        self.out(f"sw {rv}, {self._off(x)}({ro})")

    def _op_noloc(self, i, x):
        dueno = self.g.funcs.get(x.args[1])
        nombre = x.args[0]
        if self.ra.where.get(nombre) is None and dueno is not None:
            # lectura directa por la cadena de enlaces estáticos
            r = self.ra.get_dest(set())
            self.out(f"lw {r}, {self._addr(nombre, dueno)}")
            self.ra.define(x.dest, r)
            return
        r = self.ra.get_reg(nombre, set())
        self.ra.alias(x.dest, r)



class MipsGenerator:
    def __init__(self, tac, reporte, num_regs=8):
        if not 3 <= num_regs <= 8:
            raise ValueError("num_regs debe estar entre 3 y 8 (una operación necesita 3 registros)")
        self.tac = tac
        self.reporte = reporte
        self.pool = [f"$t{i}" for i in range(num_regs)]
        self.nlabel = 0
        self.stats = {}
        self._usados = []
        self._floats = {}
        self._strings = {}
        self.globals = {}
        self.class_sizes = {}
        self.funcs = {}

    def usa(self, nombre):
        if nombre not in self._usados:
            self._usados.append(nombre)

    def float_label(self, t):
        return self._floats.setdefault(t, f"__f{len(self._floats)}")

    def string_label(self, t):
        return self._strings.setdefault(t, f"__s{len(self._strings)}")


    def _preparar(self):
        r = self.reporte
        for sym, off in r.globales:
            self.globals[sym.tac_name] = off
        for cls, tam, _campos in r.clases:
            self.class_sizes[cls.name] = tam
        trozos, orden, cur = {}, [], None
        for ins in self.tac:
            if ins.op == "func_begin":
                cur = ins.dest
                trozos[cur] = []
                orden.append(cur)
            elif ins.op == "func_end":
                cur = None
            elif cur is None:
                raise CodegenError("Instrucción TAC fuera de una función.")
            else:
                trozos[cur].append(ins)
        info = {f.tac_label: (f, filas) for f, filas in r.funciones}
        for label in orden:
            fsym, filas = info.get(label, (None, []))
            params = [n for (n, cat, _o, _t) in filas if cat == "param"]
            locs = [n for (n, cat, _o, _t) in filas if cat == "local"]
            conocidos = set(params) | set(locs) | set(self.globals)
            mx = -1
            for ins in trozos[label]:
                nombres = list(_lecturas(ins))
                if ins.dest is not None and ins.op not in (
                        "label", "goto", "if_true", "if_false"):
                    nombres.append(ins.dest)
                for n in nombres:
                    m = _RE_TEMP.match(n)
                    if m and n not in conocidos:
                        mx = max(mx, int(m.group(1)))
            fi = FuncInfo(label, _asm_label(label),
                          getattr(fsym, "tac_parent_label", None),
                          params, locs, mx + 1, trozos[label])
            fi.ptipos = [_codigo_tipo(tp) for (_n, cat, _o, tp) in filas if cat == "param"]
            rt = getattr(fsym, "return_type", None)
            fi.ret = None if (fsym is None or rt is None or rt == VOID) else _codigo_tipo(rt)
            for k, n in enumerate(locs):
                fi.slot[n] = k
            for k in range(mx + 1):
                fi.slot[f"t{k}"] = len(locs) + k
            self.funcs[label] = fi
        self.orden = orden


    def generate(self):
        self._preparar()
        cuerpo = []
        for label in self.orden:
            fi = self.funcs[label]
            cuerpo.append(f"# ===== función {label} =====")
            cuerpo.extend(_Emisor(self, fi).generar())
            cuerpo.append("")
        out = [
            "# Código MIPS generado por el compilador de Compiscript",
            "# Compatible con MARS 4.5 y SPIM",
            ".text",
            ".globl main",
            "main:",
            "    la $s7, __globals          # $s7 = base de las variables globales",
            "    jal __global__             # código de nivel superior",
            "    li $v0, 10                 # exit",
            "    syscall",
            "",
        ]
        out.extend(cuerpo)
        for g in ("fatal", "print_bool", "print_str", "str_eq", "str_concat"):
            if g in self._usados:
                out.append(runtime.CODIGO[g])
        out.extend(self._datos())
        texto = _ascii("\n".join(out) + "\n")
        self.stats["instrucciones"] = sum(
            1 for ln in texto.splitlines()
            if ln.startswith("    ") and not ln.strip().startswith("#"))
        return ProgramaMIPS(texto, dict(self.stats), [self.funcs[l] for l in self.orden])

    def _datos(self):
        tam = max(WORD, self.reporte.tamano_datos_globales)
        d = [".data", ".align 2", f"__globals: .space {tam}"]
        for t, lab in self._floats.items():
            d.append(f"{lab}: .float {float(t)}")
        for g in self._usados:
            for lab, txt in runtime.DATOS.get(g, []):
                d.append(f'{lab}: .asciiz "{txt}"')
        for t, lab in self._strings.items():
            d.append(f"{lab}: {_directiva_cadena(t)}")
        return d


def _ascii(texto):

    n = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in n if ord(c) < 128)


def _directiva_cadena(lit):
    s = lit[1:-1]
    if all(32 <= ord(c) < 127 for c in s):
        # sólo se respetan \n, \t y \\ ; cualquier otra barra se escapa
        out, i = [], 0
        while i < len(s):
            c = s[i]
            if c == "\\" and i + 1 < len(s) and s[i + 1] in "nt\\":
                out.append(s[i:i + 2])
                i += 2
            elif c == "\\":
                out.append("\\\\")
                i += 1
            else:
                out.append(c)
                i += 1
        return '.asciiz "' + "".join(out) + '"'
    s = s.replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")
    datos = [b - 256 if b > 127 else b for b in s.encode("utf-8")] + [0]   
    return ".byte " + ", ".join(str(b) for b in datos)


def generar_mips(tac, reporte, num_regs=8, optimizar=True, anotar=True):

    prog = MipsGenerator(tac, reporte, num_regs).generate()
    prog.texto_original = prog.texto
    if optimizar:
        from codegen.peephole import optimizar_asm
        res = optimizar_asm(prog.texto, anotar)
        prog.texto = _ascii(res.texto)
        prog.optimizacion = res
        prog.estadisticas["instrucciones"] = res.despues
    return prog
