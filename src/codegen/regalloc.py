# -*- coding: utf-8 -*-
"""
Asignación de registros: la función getReg()
"""

INF = 10 ** 9


class RegisterAllocator:
    def __init__(self, regs, store_fn, load_fn, next_use_fn):
        self.regs = list(regs)
        self._store = store_fn          # (nombre, registro) -> emite sw
        self._load = load_fn            # (clave, registro)  -> emite lw/li/la
        self._next_use = next_use_fn    # clave -> índice de próximo uso
        self.reg_names = {r: set() for r in self.regs}
        self.where = {}
        self.in_mem = {}
        self.stats = {"loads": 0, "stores": 0, "spills": 0, "hits": 0}


    @staticmethod
    def _lit(clave):
        return clave.startswith("#")

    def _dirty(self, nombre):
        return (not self._lit(nombre)) and not self.in_mem.get(nombre, True)

    def reset(self):
        for r in self.regs:
            self.reg_names[r] = set()
        self.where.clear()
        self.in_mem.clear()

    def get_reg(self, clave, pinned=()):

        r = self.where.get(clave)
        if r is not None:
            self.stats["hits"] += 1
            return r
        r = self._pick(pinned)
        self._load(clave, r)
        self.stats["loads"] += 1
        self.reg_names[r] = {clave}
        self.where[clave] = r
        self.in_mem[clave] = True
        return r

    def get_dest(self, pinned=()):

        return self._pick(pinned)

    def define(self, dest, reg):

        self._quitar(dest)
        self.reg_names[reg] = {dest}
        self.where[dest] = reg
        self.in_mem[dest] = False

    def alias(self, dest, reg):

        if self.where.get(dest) == reg:
            self.in_mem[dest] = False
            return
        self._quitar(dest)
        self.reg_names[reg].add(dest)
        self.where[dest] = reg
        self.in_mem[dest] = False

    def _quitar(self, nombre):
        old = self.where.pop(nombre, None)
        if old is not None:
            self.reg_names[old].discard(nombre)

    def _pick(self, pinned):
        libres = [r for r in self.regs if not self.reg_names[r] and r not in pinned]
        if libres:
            return libres[0]
        cands = [r for r in self.regs if r not in pinned]
        if not cands:
            raise RuntimeError("getReg: no quedan registros disponibles")

        def costo(r):
            nombres = self.reg_names[r]
            sucio = any(self._dirty(n) for n in nombres)
            uso = min(self._next_use(n) for n in nombres)
            return (sucio, -uso)

        r = min(cands, key=costo)
        self._spill(r)
        return r

    def _spill(self, r):
        for n in list(self.reg_names[r]):
            if self._dirty(n):
                self._store(n, r)
                self.stats["stores"] += 1
                self.stats["spills"] += 1
            self.where.pop(n, None)
            self.in_mem[n] = True
        self.reg_names[r] = set()

    def flush(self):

        for r in self.regs:
            for n in self.reg_names[r]:
                if self._dirty(n):
                    self._store(n, r)
                    self.stats["stores"] += 1
        self.reset()
