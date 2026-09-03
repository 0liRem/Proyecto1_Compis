# -*- coding: utf-8 -*-


import os
import sys


#Revisa que ANTLR4 exista
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_GENERATED_DIR = os.path.join(_THIS_DIR, "generated")
for _p in (_THIS_DIR, _GENERATED_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from antlr4 import InputStream, CommonTokenStream  
from antlr4.error.Errors import RecognitionException  

from CompiscriptLexer import CompiscriptLexer  
from CompiscriptParser import CompiscriptParser  

from error_handling import ( 
    LexicalErrorListener,
    SyntaxErrorListener,
    RecoveryErrorStrategy,
    CompiscriptError,
)
from semantic.checker import analizar_semantica  


class ResultadoAnalisis:
    #Compscript

    def __init__(self, nombre_archivo, errores, arbol=None, tabla_simbolos=None):
        self.nombre_archivo = nombre_archivo
        
        self.errores = sorted(errores, key=lambda e: (e.linea, e.columna))
        self.arbol = arbol
        self.tabla_simbolos = tabla_simbolos  # Revisa si se existe la tabla de simbolos (none y sigue si explota)

    def tiene_errores(self):
        return len(self.errores) > 0

    @property
    def errores_lexicos(self):
        return [e for e in self.errores if e.tipo == "Léxico"]

    @property
    def errores_sintacticos(self):
        return [e for e in self.errores if e.tipo == "Sintáctico"]

    @property
    def errores_semanticos(self):
        return [e for e in self.errores if e.tipo == "Semántico"]


def analizar_texto(codigo: str, nombre_archivo: str = "<entrada>") -> ResultadoAnalisis:
    

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


    tabla_simbolos = None
    if arbol is not None:
        try:
            checker = analizar_semantica(arbol)
            errores = errores + checker.errors.errores
            tabla_simbolos = checker.symtab
        except RecursionError:
            errores = errores + [
                CompiscriptError(
                    "Semántico", 0, 0, "",
                    "El análisis semántico se detuvo para evitar un "
                    "desbordamiento de pila (estructura anidada demasiado "
                    "profunda, posiblemente a causa de errores previos).",
                )
            ]
        except Exception as ex:  # noqa: BLE001 - salvaguarda deliberada
            errores = errores + [
                CompiscriptError(
                    "Semántico", 0, 0, "",
                    "Ocurrió un error inesperado durante el análisis "
                    f"semántico y no se pudo completar: {ex}",
                )
            ]

    return ResultadoAnalisis(nombre_archivo, errores, arbol, tabla_simbolos)


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
              f"correctamente. No se encontraron errores léxicos, "
              f"sintácticos ni semánticos.")
    else:
        print(f"Se encontraron {len(resultado.errores)} error(es) en "
              f"'{resultado.nombre_archivo}':\n")
        for e in resultado.errores:
            print(f"[{e.tipo}] Línea {e.linea}, columna {e.columna} "
                  f"— símbolo: {e.simbolo!r}\n    {e.descripcion}\n")
