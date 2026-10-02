

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class Instruccion:
    op: str
    args: tuple = ()
    dest: Optional[str] = None
    linea: int = 0  # trazabilidad
    def __str__(self):
        a = self.args
        op = self.op

        if op == "label":
            return f"{self.dest}:"
        if op == "func_begin":
            tam = a[0] if a else 0
            return f"func {self.dest}:            ; tamaño de marco = {tam} bytes"
        if op == "func_end":
            return f"endfunc {self.dest}"
        if op == "goto":
            return f"    goto {self.dest}"
        if op == "if_true":
            return f"    if {a[0]} goto {self.dest}"
        if op == "if_false":
            return f"    ifFalse {a[0]} goto {self.dest}"
        if op == "param":
            return f"    param {a[0]}"
        if op == "call":
            etiqueta, nargs = a
            if self.dest is not None:
                return f"    {self.dest} = call {etiqueta}, {nargs}"
            return f"    call {etiqueta}, {nargs}"
        if op == "return":
            if a:
                return f"    return {a[0]}"
            return "    return"
        if op == "print":
            return f"    print {a[0]}"
        if op == "=":
            return f"    {self.dest} = {a[0]}"
        if op == "uminus":
            return f"    {self.dest} = -{a[0]}"
        if op == "not":
            return f"    {self.dest} = !{a[0]}"
        if op == "itof":
            return f"    {self.dest} = (float) {a[0]}"
        if op == "array_new":
            return f"    {self.dest} = newarray {a[0]}"
        if op == "array_load":
            return f"    {self.dest} = {a[0]}[{a[1]}]"
        if op == "array_len":
            return f"    {self.dest} = length({a[0]})"
        if op == "array_store":
            base, idx, val = a
            return f"    {base}[{idx}] = {val}"
        if op == "obj_new":
            return f"    {self.dest} = new {a[0]}"
        if op == "field_load":
            return f"    {self.dest} = {a[0]}.{a[1]}"
        if op == "field_store":
            base, campo, val = a
            return f"    {base}.{campo} = {val}"
        if op == "noloc": #no local
            return f"    {self.dest} = <no-local> {a[0]} (definida en '{a[1]}')"
        if op in ("+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||"):
            return f"    {self.dest} = {a[0]} {op} {a[1]}"
        if op == "comment":
            return f"    ; {a[0]}"

#si todo falla
        return f"    ({op} {a} -> {self.dest})"


class ProgramaTAC:
    #Orden de generacion

    def __init__(self):
        self.instrucciones = []
        self._contador_etiquetas = 0

    def nueva_etiqueta(self, prefijo="L"):
        etiqueta = f"{prefijo}{self._contador_etiquetas}"
        self._contador_etiquetas += 1
        return etiqueta

    def emit(self, op, args=(), dest=None, linea=0):
        instr = Instruccion(op, tuple(args), dest, linea=linea)
        self.instrucciones.append(instr)
        return instr

    def emit_label(self, nombre):
        self.instrucciones.append(Instruccion("label", dest=nombre))

    def __len__(self):
        return len(self.instrucciones)

    def __iter__(self):
        return iter(self.instrucciones)

    def to_text(self):
        return "\n".join(str(i) for i in self.instrucciones)
