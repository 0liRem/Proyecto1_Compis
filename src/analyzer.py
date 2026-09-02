# -*- coding: utf-8 -*-


import os
import sys


#Revisa que ANTLR4 exista
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_GENERATED_DIR = os.path.join(_THIS_DIR, "generated")
for _p in (_THIS_DIR, _GENERATED_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from antlr4 import InputStream, CommonTokenStream  # noqa: E402
from antlr4.error.Errors import RecognitionException  # noqa: E402

from CompiscriptLexer import CompiscriptLexer  # noqa: E402
from CompiscriptParser import CompiscriptParser  # noqa: E402

from error_handling import (  # noqa: E402
    LexicalErrorListener,
    SyntaxErrorListener,
    RecoveryErrorStrategy,
    CompiscriptError,
)


class ResultadoAnalisis:
    #Encapsula el resultado de analizar un programa Compiscript

    def __init__(self, nombre_archivo, errores, arbol=None):
        self.nombre_archivo = nombre_archivo
        # Se ordenan por línea y columna para presentarlos de forma coherente.
        self.errores = sorted(errores, key=lambda e: (e.linea, e.columna))
        self.arbol = arbol

    def tiene_errores(self):
        return len(self.errores) > 0

    @property
    def errores_lexicos(self):
        return [e for e in self.errores if e.tipo == "Léxico"]

    @property
    def errores_sintacticos(self):
        return [e for e in self.errores if e.tipo == "Sintáctico"]


def analizar_texto(codigo: str, nombre_archivo: str = "<entrada>") -> ResultadoAnalisis:
    """Analiza un programa Compiscript ya cargado en memoria (string)."""

    input_stream = InputStream(codigo)

    #Analisis léxic
    lexer = CompiscriptLexer(input_stream)
    lexer.removeErrorListeners()  # quitamos el listener por defecto (imprime a stderr)
    lexer_listener = LexicalErrorListener()
    lexer.addErrorListener(lexer_listener)

    tokens = CommonTokenStream(lexer)

    #Analisis sintáctico
    parser = CompiscriptParser(tokens)
    parser.removeErrorListeners()
    parser_listener = SyntaxErrorListener()
    parser.addErrorListener(parser_listener)
    parser._errHandler = RecoveryErrorStrategy()

    arbol = None
    try:
        arbol = parser.program()
    except RecognitionException as e:
        # Salvaguarda: en teoría la estrategia de recuperación evita que
        # esto se propague, pero si ocurriera se registra como un error
        # sintáctico más en vez de romper la ejecución del programa.
        parser_listener.errores.append(
            CompiscriptError(
                "Sintáctico",
                getattr(e, "line", 0),
                getattr(e, "column", 0),
                "",
                "Error sintáctico irrecuperable: la estructura del programa "
                "es demasiado ambigua a partir de este punto.",
            )
        )
    except RecursionError:
        parser_listener.errores.append(
            CompiscriptError(
                "Sintáctico",
                0,
                0,
                "",
                "El archivo contiene una estructura anidada demasiado "
                "profunda (posiblemente por errores previos) y el análisis "
                "se detuvo para evitar un desbordamiento de pila.",
            )
        )

    errores = lexer_listener.errores + parser_listener.errores
    return ResultadoAnalisis(nombre_archivo, errores, arbol)


def analizar_archivo(path: str) -> ResultadoAnalisis:
    #Analiza un archivo .cps ubicado en `path`.
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        codigo = f.read()
    return analizar_texto(codigo, nombre_archivo=path)


if __name__ == "__main__":
    # analyzer.py
    if len(sys.argv) != 2:
        print("Uso: python analyzer.py <archivo.cps>")
        sys.exit(1)

    resultado = analizar_archivo(sys.argv[1])
    if not resultado.tiene_errores():
        print(f"El archivo '{resultado.nombre_archivo}' fue analizado "
              f"correctamente. No se encontraron errores léxicos ni "
              f"sintácticos.")
    else:
        print(f"Se encontraron {len(resultado.errores)} error(es) en "
              f"'{resultado.nombre_archivo}':\n")
        for e in resultado.errores:
            print(f"[{e.tipo}] Línea {e.linea}, columna {e.columna} "
                  f"— símbolo: {e.simbolo!r}\n    {e.descripcion}\n")
