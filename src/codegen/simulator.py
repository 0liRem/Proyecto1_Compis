import math
import re
import struct
from dataclasses import dataclass

TEXT_BASE = 0x00400000
DATA_BASE = 0x10010000
HEAP_BASE = 0x10040000
STACK_TOP = 0x7FFFEFFC
STACK_SIZE = 1 << 20

REGS = {"zero": 0, "at": 1, "v0": 2, "v1": 3, "a0": 4, "a1": 5, "a2": 6, "a3": 7,
        "k0": 26, "k1": 27, "gp": 28, "sp": 29, "fp": 30, "ra": 31}
for _i in range(8):
    REGS[f"t{_i}"] = 8 + _i
    REGS[f"s{_i}"] = 16 + _i
REGS["t8"], REGS["t9"] = 24, 25


class SimuladorError(Exception):
    pass


@dataclass
class ResultadoSim:
    salida: str
    pasos: int
    codigo: int = 0


def _s32(x):
    x &= 0xFFFFFFFF
    return x - (1 << 32) if x & 0x80000000 else x


def _f(bits):
    return struct.unpack("<f", struct.pack("<I", bits & 0xFFFFFFFF))[0]


def _bits(v):
    try:
        return struct.unpack("<I", struct.pack("<f", v))[0]
    except OverflowError:
        return 0x7F800000 if v > 0 else 0xFF800000


def formato_float(bits):
    v = _f(bits)
    if math.isnan(v):
        return "NaN"
    if math.isinf(v):
        return "Infinity" if v > 0 else "-Infinity"
    if v == 0:
        return "0.0"
    for p in range(1, 10):
        t = f"{v:.{p}g}"
        if _bits(float(t)) == (bits & 0xFFFFFFFF):
            break
    d = float(t)
    if abs(d) >= 1e7 or abs(d) < 1e-3:
        m, e = f"{d:.{p}e}".split("e")
        m = m.rstrip("0")
        if m.endswith("."):
            m += "0"
        return f"{m}E{int(e)}"
    s = t if "e" not in t else f"{d:f}".rstrip("0")
    if "." not in s:
        s += ".0"
    elif s.endswith("."):
        s += "0"
    return s


def _quitar_comentario(ln):
    en, out = False, []
    for c in ln:
        if c == '"':
            en = not en
        if c == "#" and not en:
            break
        out.append(c)
    return "".join(out)


_ESC = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "0": "\0", "r": "\r"}


def _cadena(txt):
    m = re.match(r'\s*"(.*)"\s*$', txt)
    if not m:
        raise SimuladorError(f"Cadena inválida: {txt}")
    s, out, i = m.group(1), [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            out.append(_ESC.get(s[i + 1], s[i + 1]))
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out).encode("utf-8")


class MipsSimulator:
    def __init__(self, asm, max_steps=5_000_000):
        self.max_steps = max_steps
        self.instrs = []
        self.labels = {}
        self.data = bytearray()
        self.heap = bytearray()
        self.stack = bytearray(STACK_SIZE)
        self.r = [0] * 32
        self.f = [0] * 32
        self.cond = False
        self.hi = self.lo = 0
        self.out = []
        self._parse(asm)

    def _parse(self, asm):
        seccion, pend = "text", []
        for n, crudo in enumerate(asm.splitlines(), 1):
            ln = _quitar_comentario(crudo).strip()
            while True:
                m = re.match(r"^([A-Za-z_.$][\w.$]*):\s*(.*)$", ln)
                if not m:
                    break
                nom, ln = m.group(1), m.group(2)
                if seccion == "data":
                    self.labels[nom] = DATA_BASE + len(self.data)
                else:
                    self.labels[nom] = TEXT_BASE + 4 * len(self.instrs)
            if not ln:
                continue
            if ln.startswith("."):
                d, _, resto = ln.partition(" ")
                resto = resto.strip()
                if d == ".data":
                    seccion = "data"
                elif d == ".text":
                    seccion = "text"
                elif d == ".globl":
                    pass
                elif d == ".align":
                    a = 1 << int(resto)
                    while len(self.data) % a:
                        self.data.append(0)
                elif d == ".space":
                    self.data.extend(bytes(int(resto)))
                elif d == ".asciiz":
                    self.data.extend(_cadena(resto) + b"\0")
                elif d == ".ascii":
                    self.data.extend(_cadena(resto))
                elif d == ".byte":
                    self.data.extend(int(v) & 0xFF for v in resto.split(","))
                elif d in (".word", ".float"):
                    while len(self.data) % 4:
                        self.data.append(0)
                    for v in resto.split(","):
                        v = v.strip()
                        if d == ".float":
                            self.data.extend(struct.pack("<f", float(v)))
                        elif re.match(r"^-?\d+$", v):
                            self.data.extend(struct.pack("<i", int(v)))
                        else:
                            pend.append((len(self.data), v))
                            self.data.extend(bytes(4))
                else:
                    raise SimuladorError(f"Línea {n}: directiva no soportada {d}")
                continue
            mn, _, ops = ln.partition(" ")
            ops = [o.strip() for o in ops.split(",")] if ops.strip() else []
            self.instrs.append((mn, ops, n))
        for pos, v in pend:
            self.data[pos:pos + 4] = struct.pack("<I", self.labels[v])
        if "main" not in self.labels:
            raise SimuladorError("No se encontró la etiqueta 'main'.")

    def _reg(self, o):
        o = o.strip()
        if re.match(r"^\$f\d+$", o):
            return int(o[2:])
        o = o[1:]
        return int(o) if o.isdigit() else REGS[o]

    def _region(self, addr, n):
        if DATA_BASE <= addr and addr + n <= DATA_BASE + len(self.data):
            return self.data, addr - DATA_BASE
        if HEAP_BASE <= addr and addr + n <= HEAP_BASE + len(self.heap):
            return self.heap, addr - HEAP_BASE
        lo = STACK_TOP + 4 - STACK_SIZE
        if lo <= addr and addr + n <= STACK_TOP + 4:
            return self.stack, addr - lo
        raise SimuladorError(f"Acceso a memoria inválido en 0x{addr & 0xFFFFFFFF:08x}")

    def _lw(self, a):
        if a % 4:
            raise SimuladorError(f"Acceso desalineado en 0x{a & 0xFFFFFFFF:08x}")
        b, o = self._region(a & 0xFFFFFFFF, 4)
        return struct.unpack_from("<i", b, o)[0]

    def _sw(self, a, v):
        if a % 4:
            raise SimuladorError(f"Acceso desalineado en 0x{a & 0xFFFFFFFF:08x}")
        b, o = self._region(a & 0xFFFFFFFF, 4)
        struct.pack_into("<I", b, o, v & 0xFFFFFFFF)

    def _addr(self, op):
        m = re.match(r"^(-?\w+)?\((\$\w+)\)$", op)
        if m:
            off = int(m.group(1)) if m.group(1) else 0
            return _s32(self.r[self._reg(m.group(2))] + off)
        m = re.match(r"^([A-Za-z_.$][\w.$]*)(?:\s*\+\s*(\d+))?$", op)
        if m and m.group(1) in self.labels:
            return self.labels[m.group(1)] + int(m.group(2) or 0)
        raise SimuladorError(f"Operando de memoria inválido: {op}")

    # ---------------- ejecución ----------------
    def run(self, trace=None):
        """trace: objeto opcional con llamar(sim, etiqueta) y retornar(sim)."""
        r, f = self.r, self.f
        r[29] = STACK_TOP
        r[28] = DATA_BASE + 0x8000
        pc = (self.labels["main"] - TEXT_BASE) // 4
        pasos = 0
        n_ins = len(self.instrs)
        W = lambda i, v: r.__setitem__(i, _s32(v)) if i else None  # noqa: E731
        R = self._reg
        while True:
            if not 0 <= pc < n_ins:
                raise SimuladorError("El programa salió del segmento de código.")
            pasos += 1
            if pasos > self.max_steps:
                raise SimuladorError(
                    f"Se superó el límite de {self.max_steps} instrucciones "
                    "(¿bucle infinito?).")
            mn, o, ln = self.instrs[pc]
            pc += 1
            try:
                if mn == "li":
                    W(R(o[0]), int(o[1], 0))
                elif mn == "la":
                    W(R(o[0]), self.labels[o[1]])
                elif mn == "move":
                    W(R(o[0]), r[R(o[1])])
                elif mn == "lw":
                    W(R(o[0]), self._lw(self._addr(o[1])))
                elif mn == "sw":
                    self._sw(self._addr(o[1]), r[R(o[0])])
                elif mn == "lb":
                    b, off = self._region(self._addr(o[1]) & 0xFFFFFFFF, 1)
                    v = b[off]
                    W(R(o[0]), v - 256 if v > 127 else v)
                elif mn == "sb":
                    b, off = self._region(self._addr(o[1]) & 0xFFFFFFFF, 1)
                    b[off] = r[R(o[0])] & 0xFF
                elif mn in ("addu", "add"):
                    W(R(o[0]), r[R(o[1])] + r[R(o[2])])
                elif mn in ("subu", "sub"):
                    W(R(o[0]), r[R(o[1])] - r[R(o[2])])
                elif mn in ("addiu", "addi"):
                    W(R(o[0]), r[R(o[1])] + int(o[2], 0))
                elif mn == "mul":
                    W(R(o[0]), r[R(o[1])] * r[R(o[2])])
                elif mn == "div":
                    a, b = r[R(o[0])], r[R(o[1])]
                    if b:
                        q = abs(a) // abs(b)
                        q = q if (a < 0) == (b < 0) else -q
                        self.lo, self.hi = q, a - q * b
                elif mn == "mflo":
                    W(R(o[0]), self.lo)
                elif mn == "mfhi":
                    W(R(o[0]), self.hi)
                elif mn == "slt":
                    W(R(o[0]), int(r[R(o[1])] < r[R(o[2])]))
                elif mn == "sltu":
                    W(R(o[0]), int((r[R(o[1])] & 0xFFFFFFFF) < (r[R(o[2])] & 0xFFFFFFFF)))
                elif mn == "sltiu":
                    W(R(o[0]), int((r[R(o[1])] & 0xFFFFFFFF) < (int(o[2], 0) & 0xFFFFFFFF)))
                elif mn == "xori":
                    W(R(o[0]), r[R(o[1])] ^ int(o[2], 0))
                elif mn == "sll":
                    W(R(o[0]), r[R(o[1])] << int(o[2], 0))
                elif mn == "beqz":
                    if r[R(o[0])] == 0:
                        pc = (self.labels[o[1]] - TEXT_BASE) // 4
                elif mn == "bnez":
                    if r[R(o[0])] != 0:
                        pc = (self.labels[o[1]] - TEXT_BASE) // 4
                elif mn == "beq":
                    if r[R(o[0])] == r[R(o[1])]:
                        pc = (self.labels[o[2]] - TEXT_BASE) // 4
                elif mn == "bne":
                    if r[R(o[0])] != r[R(o[1])]:
                        pc = (self.labels[o[2]] - TEXT_BASE) // 4
                elif mn == "j":
                    pc = (self.labels[o[0]] - TEXT_BASE) // 4
                elif mn == "jal":
                    if trace is not None:
                        trace.llamar(self, o[0])
                    r[31] = TEXT_BASE + 4 * pc
                    pc = (self.labels[o[0]] - TEXT_BASE) // 4
                elif mn == "jr":
                    if trace is not None and R(o[0]) == 31:
                        trace.retornar(self)
                    pc = ((r[R(o[0])] & 0xFFFFFFFF) - TEXT_BASE) // 4
                elif mn == "mtc1":
                    f[R(o[1])] = r[R(o[0])] & 0xFFFFFFFF
                elif mn == "mfc1":
                    W(R(o[0]), f[R(o[1])])
                elif mn in ("add.s", "sub.s", "mul.s", "div.s"):
                    a, b = _f(f[R(o[1])]), _f(f[R(o[2])])
                    if mn == "add.s":
                        v = a + b
                    elif mn == "sub.s":
                        v = a - b
                    elif mn == "mul.s":
                        v = a * b
                    else:
                        v = (a / b) if b else (math.copysign(math.inf, a) if a else math.nan)
                    f[R(o[0])] = _bits(v)
                elif mn == "neg.s":
                    f[R(o[0])] = f[R(o[1])] ^ 0x80000000
                elif mn == "cvt.s.w":
                    f[R(o[0])] = _bits(float(_s32(f[R(o[1])])))
                elif mn == "c.lt.s":
                    self.cond = _f(f[R(o[0])]) < _f(f[R(o[1])])
                elif mn == "c.le.s":
                    self.cond = _f(f[R(o[0])]) <= _f(f[R(o[1])])
                elif mn == "c.eq.s":
                    self.cond = _f(f[R(o[0])]) == _f(f[R(o[1])])
                elif mn == "bc1t":
                    if self.cond:
                        pc = (self.labels[o[0]] - TEXT_BASE) // 4
                elif mn == "bc1f":
                    if not self.cond:
                        pc = (self.labels[o[0]] - TEXT_BASE) // 4
                elif mn == "nop":
                    pass
                elif mn == "syscall":
                    v0 = r[2]
                    if v0 == 1:
                        self.out.append(str(r[4]))
                    elif v0 == 2:
                        self.out.append(formato_float(f[12]))
                    elif v0 == 4:
                        a, s = r[4] & 0xFFFFFFFF, bytearray()
                        while True:
                            b, off = self._region(a, 1)
                            if b[off] == 0:
                                break
                            s.append(b[off])
                            a += 1
                        self.out.append(s.decode("utf-8", errors="replace"))
                    elif v0 == 9:
                        n = (r[4] + 3) & ~3
                        W(2, HEAP_BASE + len(self.heap))
                        self.heap.extend(bytes(n))
                    elif v0 == 10:
                        return ResultadoSim("".join(self.out), pasos, 0)
                    elif v0 == 11:
                        self.out.append(chr(r[4] & 0xFF))
                    elif v0 == 17:
                        return ResultadoSim("".join(self.out), pasos, r[4])
                    else:
                        raise SimuladorError(f"syscall {v0} no soportada")
                else:
                    raise SimuladorError(f"instrucción no soportada: {mn}")
            except SimuladorError as e:
                raise SimuladorError(f"Línea {ln}: {e}") from None
            except (KeyError, IndexError, ValueError) as e:
                raise SimuladorError(f"Línea {ln}: operando inválido en '{mn}' ({e})") from None
