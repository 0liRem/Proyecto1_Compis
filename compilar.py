#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compilador de Compiscript por línea de comandos.

  python compilar.py programa.cps                 # genera programa.asm
  python compilar.py programa.cps -o salida.asm
  python compilar.py programa.cps --run           # compila y ejecuta
  python compilar.py programa.cps --run --sim mars|spim|integrado|auto
  python compilar.py programa.cps --tac           # muestra además el TAC
  python compilar.py programa.cps --no-opt        # sin optimización por mirilla
  python compilar.py programa.cps --arbol         # árbol de activación (texto)
  python compilar.py programa.cps --arbol-png a.png   # árbol de activación (imagen)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from analyzer import analizar_archivo  # noqa: E402
from codegen.runner import ejecutar, simuladores_disponibles  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compilador Compiscript -> MIPS")
    ap.add_argument("archivo")
    ap.add_argument("-o", "--salida")
    ap.add_argument("--run", action="store_true", help="ejecutar en un simulador")
    ap.add_argument("--sim", default="auto", help="auto | integrado | mars | spim")
    ap.add_argument("--tac", action="store_true", help="imprimir el código intermedio")
    ap.add_argument("--regs", type=int, default=8, help="registros $t disponibles para getReg (3-8)")
    ap.add_argument("--no-opt", action="store_true", help="desactiva la optimización por mirilla")
    ap.add_argument("--arbol", action="store_true", help="imprime el árbol de activación")
    ap.add_argument("--arbol-png", metavar="ARCHIVO", help="guarda el árbol de activación como imagen")
    a = ap.parse_args(argv)

    from analyzer import analizar_texto
    with open(a.archivo, encoding="utf-8", errors="replace") as f:
        res = analizar_texto(f.read(), a.archivo, num_regs=a.regs, optimizar=not a.no_opt)
    if res.tiene_errores():
        print(f"{len(res.errores)} error(es) en '{a.archivo}':")
        for e in res.errores:
            print(f"  [{e.tipo}] línea {e.linea}, col {e.columna}: {e.descripcion}")
        return 1
    if res.error_mips:
        print("No se pudo generar MIPS:", res.error_mips)
        return 2
    if a.tac:
        print(res.codigo_intermedio.to_text(), "\n")
    destino = a.salida or os.path.splitext(a.archivo)[0] + ".asm"
    with open(destino, "w", encoding="utf-8") as f:
        f.write(res.codigo_mips.texto)
    print(f"Ensamblador MIPS escrito en {destino}")
    if res.codigo_mips.optimizacion is not None:
        print(res.codigo_mips.optimizacion.resumen())
    if a.arbol or a.arbol_png:
        from codegen.activation_tree import trazar, export_activation_image
        arbol = trazar(res.codigo_mips)
        if a.arbol:
            print("--- árbol de activación ---")
            print(arbol.to_text())
        if a.arbol_png:
            base = os.path.splitext(a.arbol_png)[0]
            ruta = export_activation_image(arbol, base, "png", f"Árbol de activación — {os.path.basename(a.archivo)}")
            print(f"Árbol de activación guardado en {ruta}")
    if a.run:
        r = ejecutar(res.codigo_mips.texto, a.sim)
        print(f"--- salida ({r.simulador}) ---")
        print(r.salida, end="")
        if not r.ok:
            print(f"--- error de ejecución: {r.error}")
            return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
