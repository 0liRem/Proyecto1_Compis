# -*- coding: utf-8 -*-


import re
from antlr4.error.ErrorListener import ErrorListener
from antlr4.error.ErrorStrategy import DefaultErrorStrategy
from antlr4.Token import Token


#nombres y simbolos

FRIENDLY_TOKENS = {
    # Delimitadores y puntuación
    "'{'": "la llave de apertura '{'",
    "'}'": "la llave de cierre '}'",
    "'('": "el paréntesis de apertura '('",
    "')'": "el paréntesis de cierre ')'",
    "'['": "el corchete de apertura '['",
    "']'": "el corchete de cierre ']'",
    "';'": "el punto y coma ';'",
    "','": "la coma ','",
    "':'": "los dos puntos ':'",
    "'.'": "el punto '.'",
    "'='": "el signo de asignación '='",
    # Operadores
    "'=='": "el operador de igualdad '=='",
    "'!='": "el operador de desigualdad '!='",
    "'<'": "el operador relacional '<'",
    "'<='": "el operador relacional '<='",
    "'>'": "el operador relacional '>'",
    "'>='": "el operador relacional '>='",
    "'+'": "el operador '+'",
    "'-'": "el operador '-'",
    "'*'": "el operador '*'",
    "'/'": "el operador '/'",
    "'%'": "el operador '%'",
    "'!'": "el operador de negación '!'",
    "'?'": "el operador ternario '?'",
    "'||'": "el operador lógico '||'",
    "'&&'": "el operador lógico '&&'",
    # Palabras reservadas
    "'let'": "la palabra reservada 'let'",
    "'var'": "la palabra reservada 'var'",
    "'const'": "la palabra reservada 'const'",
    "'if'": "la palabra reservada 'if'",
    "'else'": "la palabra reservada 'else'",
    "'while'": "la palabra reservada 'while'",
    "'do'": "la palabra reservada 'do'",
    "'for'": "la palabra reservada 'for'",
    "'foreach'": "la palabra reservada 'foreach'",
    "'in'": "la palabra reservada 'in'",
    "'break'": "la palabra reservada 'break'",
    "'continue'": "la palabra reservada 'continue'",
    "'return'": "la palabra reservada 'return'",
    "'try'": "la palabra reservada 'try'",
    "'catch'": "la palabra reservada 'catch'",
    "'switch'": "la palabra reservada 'switch'",
    "'case'": "la palabra reservada 'case'",
    "'default'": "la palabra reservada 'default'",
    "'function'": "la palabra reservada 'function'",
    "'class'": "la palabra reservada 'class'",
    "'print'": "la palabra reservada 'print'",
    "'new'": "la palabra reservada 'new'",
    "'this'": "la palabra reservada 'this'",
    "'null'": "el literal 'null'",
    "'true'": "el literal booleano 'true'",
    "'false'": "el literal booleano 'false'",
    "'boolean'": "el tipo 'boolean'",
    "'integer'": "el tipo 'integer'",
    "'string'": "el tipo 'string'",
    # Tokens no literales
    "Identifier": "un identificador (nombre de variable, función o clase)",
    "Literal": "un valor literal (número o cadena de texto)",
    "IntegerLiteral": "un número entero",
    "StringLiteral": "una cadena de texto",
    "EOF": "el final del archivo",
    "'<EOF>'": "el final del archivo",
    "<EOF>": "el final del archivo",
}


def friendly(tok: str) -> str:

    tok = tok.strip()
    if tok in FRIENDLY_TOKENS:
        return FRIENDLY_TOKENS[tok]
    if tok.startswith("'") and tok.endswith("'") and len(tok) >= 2:
        return f"'{tok[1:-1]}'"
    return tok



_TOKEN_ITEM_RE = re.compile(r"'(?:\\.|[^'\\])*'|[A-Za-z_][A-Za-z0-9_]*")


def parse_expected_set(raw: str):
    """Recibe el contenido entre llaves de un mensaje 'expecting {...}' y
    devuelve una lista de descripciones amigables, sin duplicados."""
    items = _TOKEN_ITEM_RE.findall(raw)
    vistos = []
    for it in items:
        f = friendly(it)
        if f not in vistos:
            vistos.append(f)
    return vistos


def humanize_list(items) -> str:
    """Convierte ['a', 'b', 'c'] en la cadena 'a, b o c'."""
    if not items:
        return "un símbolo distinto"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " o " + items[-1]



# Traductor de errores

_MISSING_RE = re.compile(r"^missing (.+?) at (.+)$")
_MISMATCHED_RE = re.compile(r"^mismatched input (.+?) expecting (.+)$")
_EXTRANEOUS_RE = re.compile(r"^extraneous input (.+?) expecting (.+)$")
_NOVIABLE_RE = re.compile(r"^no viable alternative at input (.+)$")


def _expand_expecting(expecting: str) -> str:
    expecting = expecting.strip()
    if expecting.startswith("{") and expecting.endswith("}"):
        items = parse_expected_set(expecting[1:-1])
        return humanize_list(items)
    return friendly(expecting)


def translate_parser_msg(msg: str) -> str:

    m = _MISSING_RE.match(msg)
    if m:
        falta, en = m.group(1), m.group(2)
        return (
            f"Falta {friendly(falta)}. Se esperaba encontrarlo antes de "
            f"{friendly(en)}."
        )

    m = _MISMATCHED_RE.match(msg)
    if m:
        sym, expecting = m.group(1), m.group(2)
        return (
            f"Se encontró {friendly(sym)}, pero en este punto del programa "
            f"se esperaba {_expand_expecting(expecting)}."
        )

    m = _EXTRANEOUS_RE.match(msg)
    if m:
        sym, expecting = m.group(1), m.group(2)
        return (
            f"El símbolo {friendly(sym)} no es válido en este punto; "
            f"se esperaba {_expand_expecting(expecting)}."
        )

    m = _NOVIABLE_RE.match(msg)
    if m:
        sym = m.group(1)
        return (
            f"No se reconoce una estructura válida del lenguaje a partir de "
            f"{friendly(sym)}."
        )
    #Si no matchea regresa el error original
    return f"Error sintáctico: {msg}"


_LEXER_RE = re.compile(r"^token recognition error at: '(.*)'$", re.DOTALL)


def translate_lexer_msg(msg: str):
    """Traduce un mensaje léxico crudo de ANTLR a una descripción clara en
    español. Devuelve una tupla (descripcion, lexema)."""
    m = _LEXER_RE.match(msg)
    if m:
        texto = m.group(1)
        texto_mostrar = texto.rstrip("\r\n")
        if texto.startswith('"'):
            return (
                "Cadena de texto no cerrada: falta la comilla doble (\") "
                "de cierre antes de que termine la línea.",
                texto_mostrar,
            )
        if len(texto_mostrar) > 30:
            texto_mostrar = texto_mostrar[:30] + "…"
        return (
            f"Carácter o símbolo no reconocido por el lenguaje Compiscript: "
            f"'{texto_mostrar}'.",
            texto_mostrar,
        )
    return (f"Error léxico: {msg}", "")



#Estructura de datos para representar un error


class CompiscriptError:
    """Representa un único error léxico o sintáctico ya traducido y listo
    para mostrarse al usuario."""

    def __init__(self, tipo, linea, columna, simbolo, descripcion):
        self.tipo = tipo                # "Léxico" | "Sintáctico"
        self.linea = linea              # número de línea (1-based, tal como lo entrega ANTLR)
        self.columna = columna + 1      # ANTLR reporta columna 0-based; la mostramos 1-based
        self.simbolo = simbolo if simbolo else "(sin símbolo)"
        self.descripcion = descripcion

    def __repr__(self):
        return (f"CompiscriptError(tipo={self.tipo!r}, linea={self.linea}, "
                f"columna={self.columna}, simbolo={self.simbolo!r})")

    def as_dict(self):
        return {
            "tipo": self.tipo,
            "linea": self.linea,
            "columna": self.columna,
            "simbolo": self.simbolo,
            "descripcion": self.descripcion,
        }


# Listeners de error

class LexicalErrorListener(ErrorListener):
    """Escucha los errores del lexer. No detiene el análisis: el propio
    lexer generado por ANTLR ya se recupera automáticamente saltando el
    carácter (o la cadena de texto) que no pudo reconocer y continúa
    escaneando el resto del archivo."""

    def __init__(self):
        super().__init__()
        self.errores = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        descripcion, lexema = translate_lexer_msg(msg)
        self.errores.append(
            CompiscriptError("Léxico", line, column, lexema, descripcion)
        )






class SyntaxErrorListener(ErrorListener):


    def __init__(self):
        super().__init__()
        self.errores = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        descripcion = translate_parser_msg(msg)
        simbolo = offendingSymbol.text if offendingSymbol is not None else "<fin de archivo>"
        self.errores.append(
            CompiscriptError("Sintáctico", line, column, simbolo, descripcion)
        )



#Estrategia de recuperación sintáctica en modo pánico


class RecoveryErrorStrategy(DefaultErrorStrategy):


    def __init__(self):
        super().__init__()
        self._ultimo_indice_error = -1

    def recover(self, recognizer, e):
        stream = recognizer.getInputStream()
        indice_actual = stream.index
        if indice_actual == self._ultimo_indice_error:
            if stream.LA(1) != Token.EOF:
                recognizer.consume()
        self._ultimo_indice_error = stream.index
        super().recover(recognizer, e)

    def recoverInline(self, recognizer):
        stream = recognizer.getInputStream()
        self._ultimo_indice_error = stream.index
        return super().recoverInline(recognizer)
