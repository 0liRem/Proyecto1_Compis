# -*- coding: utf-8 -*-


import glob
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Optional

from codegen.simulator import MipsSimulator, SimuladorError

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class ResultadoEjecucion:
    salida: str
    simulador: str
    ok: bool
    error: str = ""
    duracion: float = 0.0
    pasos: Optional[int] = None


def buscar_mars(ruta=None):
    java = shutil.which("java")
    if not java:
        return None
    cands = [ruta, os.environ.get("MARS_JAR")]
    for base in (os.path.join(_RAIZ, "tools"), _RAIZ, os.getcwd()):
        cands += sorted(glob.glob(os.path.join(base, "[Mm]ars*.jar")))
    for c in cands:
        if c and os.path.isfile(c):
            return (java, c)
    return None


def buscar_spim(ruta=None):
    cands = [ruta, os.environ.get("SPIM_PATH"), shutil.which("spim"), shutil.which("spim.exe")]
    if os.name == "nt":
        for pf in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
            if pf:
                cands += glob.glob(os.path.join(pf, "*pim*", "spim.exe"))
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def simuladores_disponibles(config=None):
    """dict nombre -> descripción de los simuladores utilizables."""
    config = config or {}
    d = {"integrado": "Simulador integrado (Python)"}
    m = buscar_mars(config.get("mars"))
    if m:
        d["mars"] = f"MARS ({os.path.basename(m[1])})"
    s = buscar_spim(config.get("spim"))
    if s:
        d["spim"] = f"SPIM ({s})"
    return d


def _limpiar_spim(txt):
    ln = [l for l in txt.splitlines()
          if not re.match(r"^(SPIM Version|Copyright|All Rights|See the file README|Loaded:)", l)]
    return "\n".join(ln) + ("\n" if txt.endswith("\n") else "")


def ejecutar(asm, simulador="auto", timeout=20, max_pasos=5_000_000, config=None):
    config = config or {}
    disp = simuladores_disponibles(config)
    if simulador == "auto":
        simulador = "mars" if "mars" in disp else ("spim" if "spim" in disp else "integrado")
    if simulador not in disp:
        return ResultadoEjecucion("", simulador, False,
                                  f"El simulador '{simulador}' no está disponible en este equipo.")
    t0 = time.time()
    if simulador == "integrado":
        try:
            r = MipsSimulator(asm, max_pasos).run()
            return ResultadoEjecucion(r.salida, simulador, True, "", time.time() - t0, r.pasos)
        except SimuladorError as e:
            return ResultadoEjecucion("", simulador, False, str(e), time.time() - t0)
    fd, ruta = tempfile.mkstemp(suffix=".asm")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(asm)
        if simulador == "mars":
            java, jar = buscar_mars(config.get("mars"))
            cmd = [java, "-Djava.awt.headless=true", "-jar", jar, "nc", ruta]
        else:
            cmd = [buscar_spim(config.get("spim")), "-file", ruta]
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return ResultadoEjecucion("", simulador, False,
                                      f"Tiempo de ejecución excedido ({timeout} s).", time.time() - t0)
        out = p.stdout.decode("utf-8", errors="replace")
        err = p.stderr.decode("utf-8", errors="replace")
        if simulador == "spim":
            out = _limpiar_spim(out)
        if simulador == "mars":
            if out.endswith("\n"):
                out = out[:-1]    # MARS siempre agrega un salto de línea al terminar
            try:                  # MARS escribe cada byte como un carácter Latin-1
                out = out.encode("latin-1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        if simulador == "mars":   # MARS informa errores de ensamblado/ejecución por stderr o stdout
            err = "\n".join(l for l in err.splitlines()
                            if "java.util.prefs" not in l and not l.startswith("INFO")).strip()
        ok = p.returncode == 0 and not (simulador == "mars" and err)
        return ResultadoEjecucion(out, simulador, ok, err if not ok else "", time.time() - t0)
    finally:
        try:
            os.remove(ruta)
        except OSError:
            pass
