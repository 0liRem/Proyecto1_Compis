
#Error_handling 2.0
from error_handling import CompiscriptError


class SemanticErrors:
    def __init__(self):
        self.errores = []
        self._seen = set()

    def add(self, line, col, symbol, descripcion):
        key = (line, col, descripcion)
        if key in self._seen:
            return
        self._seen.add(key)
        self.errores.append(CompiscriptError("Semántico", line, col, symbol, descripcion))

    def report(self, ctx, descripcion, symbol=""):
        #ANTLR errors
        tok = ctx.start
        self.add(tok.line, tok.column, symbol or tok.text, descripcion)

    def __len__(self):
        return len(self.errores)
