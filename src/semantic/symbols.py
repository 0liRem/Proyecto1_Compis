# -*- coding: utf-8 -*-
"""
Tabla de símbolos y manejo de entornos COMPSCRIPT

tabla de simbolos exportarla para mostrarla

QUE NO SE ME OLVIDE

    Tengo que añadir tabla de simbolos visual
    LAS REGLAS DE SIMBOLOS
    SCOPES
    SCOPES (hater)
"""


class Symbol:
    def __init__(self, name, sym_type=None, line=0, col=0):
        self.name = name
        self.type = sym_type
        self.line = line
        self.col = col

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name!r}: {self.type})"


class VariableSymbol(Symbol):
    def __init__(self, name, sym_type=None, line=0, col=0, is_const=False):
        super().__init__(name, sym_type, line, col)
        self.is_const = is_const
        self.initialized = False


class FunctionSymbol(Symbol):
    def __init__(self, name, param_types, param_names, return_type, line=0, col=0):
        super().__init__(name, return_type, line, col)
        self.param_types = list(param_types)
        self.param_names = list(param_names)
        self.return_type = return_type
        self.scope = None          # Scope body
        self.owner_class = None    # ClassSymbol para los metodos
        self.is_recursive_call_site = False


class ClassSymbol(Symbol):
    def __init__(self, name, line=0, col=0):
        super().__init__(name, sym_type=None, line=line, col=col)
        self.superclass = None       # ClassSymbol o None
        self.superclass_name = None 
        self.fields = {}             
        self.methods = {}            # funciones
        self.constructor = None      # Si es funcion
        self.scope = None            # scope clase

#Encontrar campo
    def find_field(self, name, _visited=None):
        _visited = _visited or set()
        if id(self) in _visited:
            return None
        _visited.add(id(self))
        if name in self.fields:
            return self.fields[name]
        if self.superclass is not None:
            return self.superclass.find_field(name, _visited)
        return None

#Encontrar si es metodo
    def find_method(self, name, _visited=None):
        _visited = _visited or set()
        if id(self) in _visited:
            return None
        _visited.add(id(self))
        if name in self.methods:
            return self.methods[name]
        if self.superclass is not None:
            return self.superclass.find_method(name, _visited)
        return None

    def find_member(self, name):
        return self.find_field(name) or self.find_method(name)


    #HERENCIA DE CONSTRUCTORES GLOBALES y declaracion de impuestos
    def find_constructor(self, _visited=None):
        _visited = _visited or set()
        if id(self) in _visited:
            return None
        _visited.add(id(self))
        if self.constructor is not None:
            return self.constructor
        if self.superclass is not None:
            return self.superclass.find_constructor(_visited)
        return None


class Scope:
    """
    global, function, block, class, loop
    """

    def __init__(self, kind, parent=None, label=""):
        self.kind = kind
        self.parent = parent
        self.label = label
        self.symbols = {}
        self.children = []
        if parent is not None:
            parent.children.append(self)

    def define(self, symbol: Symbol) -> bool:
        #simbolo para el entorno
        if symbol.name in self.symbols:
            return False
        self.symbols[symbol.name] = symbol
        return True

    def resolve_local(self, name):
        return self.symbols.get(name)

    def resolve(self, name):
       # Busca name en este entorno y si no esta en los entornos contenedores padres hasta el entorno global
        scope = self
        while scope is not None:
            if name in scope.symbols:
                return scope.symbols[name]
            scope = scope.parent
        return None

    def enclosing_of_kind(self, kind):
        scope = self
        while scope is not None:
            if scope.kind == kind:
                return scope
            scope = scope.parent
        return None

    def enclosing_function_scope(self):
        return self.enclosing_of_kind("function")

    def enclosing_class_scope(self):
        return self.enclosing_of_kind("class")

    def is_inside_loop(self):
        #Revisa si esta en un loop
        scope = self
        while scope is not None:
            if scope.kind == "loop":
                return True
            if scope.kind == "function":
                return False
            scope = scope.parent
        return False

    def is_inside_loop_or_switch(self):
        scope = self
        while scope is not None:
            if scope.kind in ("loop", "switch"):
                return True
            if scope.kind == "function":
                return False
            scope = scope.parent
        return False

    def dump(self, indent=0):
        pad = "  " * indent
        lines = [f"{pad}[{self.kind}] {self.label}"]
        for sym in self.symbols.values():
            lines.append(f"{pad}  - {sym!r}")
        for child in self.children:
            lines.append(child.dump(indent + 1))
        return "\n".join(lines)

#Hu
class SymbolTable:
    def __init__(self):
        self.global_scope = Scope("global", parent=None, label="global")
        self.current = self.global_scope
        self.operation_log = []

    def _scope_name(self, scope=None):
        scope = scope or self.current
        path = []
        while scope is not None:
            path.append(scope.label or scope.kind)
            scope = scope.parent
        return " / ".join(reversed(path))

    def insert(self, symbol: Symbol, scope=None) -> bool:
        scope = scope or self.current
        ok = scope.define(symbol)
        self.operation_log.append({
            "operation": "INSERTAR",
            "name": symbol.name,
            "type": str(symbol.type) if symbol.type is not None else "-",
            "scope": self._scope_name(scope),
            "result": "OK" if ok else "DUPLICADO",
        })
        return ok

    def retrieve(self, name, scope=None):
        scope = scope or self.current
        symbol = scope.resolve(name)
        self.operation_log.append({
            "operation": "RECUPERAR",
            "name": name,
            "type": str(symbol.type) if symbol is not None and symbol.type is not None else "-",
            "scope": self._scope_name(scope),
            "result": "ENCONTRADO" if symbol is not None else "NO ENCONTRADO",
        })
        return symbol

    def update(self, symbol: Symbol, **changes):
        #actualiza y registrar operaciones
        for key, value in changes.items():
            setattr(symbol, key, value)
        self.operation_log.append({
            "operation": "ACTUALIZAR",
            "name": symbol.name,
            "type": str(symbol.type) if symbol.type is not None else "-",
            "scope": self._scope_name(self._find_scope(symbol)),
            "result": ", ".join(changes.keys()) or "sin cambios",
        })
        return symbol

    def _find_scope(self, symbol, scope=None):
        scope = scope or self.global_scope
        if scope.symbols.get(symbol.name) is symbol:
            return scope
        for child in scope.children:
            found = self._find_scope(symbol, child)
            if found is not None:
                return found
        return self.current

    def enter(self, scope):
        self.current = scope
        self.operation_log.append({
            "operation": "ENTRAR ALCANCE",
            "name": "-",
            "type": "-",
            "scope": self._scope_name(scope),
            "result": scope.kind,
        })
        return scope

    def push(self, kind, label=""):
        return self.enter(Scope(kind, parent=self.current, label=label))

    def pop(self):
        assert self.current.parent is not None, "No se puede sacar el entorno global"
        leaving = self.current
        self.current = self.current.parent
        self.operation_log.append({
            "operation": "SALIR ALCANCE",
            "name": "-",
            "type": "-",
            "scope": self._scope_name(self.current),
            "result": leaving.label or leaving.kind,
        })
        return self.current

    def dump(self):
        return self.global_scope.dump()

    def clear_operation_log(self):
        self.operation_log.clear()
