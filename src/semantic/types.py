# -*- coding: utf-8 -*-
"""
Sistema de tipos de Compiscript.

Siga corriendo aunque falle
Lista de regl
"""

#Tipos
class Type:

    def is_error(self) -> bool:
        return False

    def is_numeric(self) -> bool:
        return False

    def is_void(self) -> bool:
        return False

    def __eq__(self, other):
        return isinstance(other, Type) and str(self) == str(other)

    def __hash__(self):
        return hash(str(self))

    def __repr__(self):
        return f"<Type {str(self)}>"


class PrimitiveType(Type):
    _instances = {}

    def __new__(cls, name):
        if name not in cls._instances:
            inst = super().__new__(cls)
            cls._instances[name] = inst
        return cls._instances[name]

    def __init__(self, name):
        self.name = name

    def is_numeric(self):
        return self.name in ("integer", "float")

    def is_void(self):
        return self.name == "void"

    def __str__(self):
        return self.name


INTEGER = PrimitiveType("integer")
FLOAT = PrimitiveType("float")
BOOLEAN = PrimitiveType("boolean")
STRING = PrimitiveType("string")
VOID = PrimitiveType("void")
NULL = PrimitiveType("null")

#Tipos de errores
class ErrorType(Type):

    def is_error(self):
        return True

    def is_numeric(self):
        return True

    def __eq__(self, other):
        return True

    def __hash__(self):
        return 0

    def __str__(self):
        return "<tipo desconocido>"


ERROR = ErrorType()

#tipos arreglos
class ArrayType(Type):
    def __init__(self, element_type: Type):
        self.element_type = element_type

    def __eq__(self, other):
        if isinstance(other, ErrorType):
            return True
        return isinstance(other, ArrayType) and self.element_type == other.element_type

    def __hash__(self):
        return hash(("array", self.element_type))

    def __str__(self):
        return f"{self.element_type}[]"


#tipos de clase
class ClassType(Type):


    def __init__(self, name: str, symbol=None):
        self.name = name
        self.symbol = symbol 

    def __eq__(self, other):
        if isinstance(other, ErrorType):
            return True
        return isinstance(other, ClassType) and self.name == other.name

    def __hash__(self):
        return hash(("class", self.name))

    def __str__(self):
        return self.name

#tipos de funciones
class FunctionType(Type):

    def __init__(self, param_types, return_type: Type):
        self.param_types = list(param_types)
        self.return_type = return_type

    def __eq__(self, other):
        if isinstance(other, ErrorType):
            return True
        return (
            isinstance(other, FunctionType)
            and self.param_types == other.param_types
            and self.return_type == other.return_type
        )

    def __hash__(self):
        return hash(("function", tuple(self.param_types), self.return_type))

    def __str__(self):
        params = ", ".join(str(p) for p in self.param_types)
        return f"({params}) -> {self.return_type}"


# Reglas de compatibilidad


_PRIMITIVE_NAMES = {
    "integer": INTEGER,
    "float": FLOAT,
    "boolean": BOOLEAN,
    "string": STRING,
    "void": VOID,
}


def primitive_from_name(name: str):
#Basetype regresa el nombre
    return _PRIMITIVE_NAMES.get(name)


#es numerico
def is_numeric(t: Type) -> bool:
    return t.is_error() or t.is_numeric()


#Ciclos de herencia 
def class_is_subtype(sub, sup) -> bool:
    visited = set()
    current = sub
    while current is not None and id(current) not in visited:
        if current is sup or current.name == sup.name:
            return True
        visited.add(id(current))
        current = current.superclass
    return False


#Revisa que a la variable se le asigne bien las chivas
def is_assignable(target: Type, value: Type) -> bool:
    if target.is_error() or value.is_error():
        return True
    if target == value:
        return True
    # Ensanchamiento numérico: integer -> float
    if target == FLOAT and value == INTEGER:
        return True
    # null es asignable a cualquier tipo referencia (clase o arreglo)
    if value == NULL and isinstance(target, (ClassType, ArrayType)):
        return True
    # Polimorfismo: una subclase es asignable a una variable de la superclase
    if isinstance(target, ClassType) and isinstance(value, ClassType):
        if target.symbol is not None and value.symbol is not None:
            return class_is_subtype(value.symbol, target.symbol)
    if isinstance(target, ArrayType) and isinstance(value, ArrayType):
        return is_assignable(target.element_type, value.element_type)
    return False

#No integer y float 
def are_comparable(a: Type, b: Type) -> bool:
    if a.is_error() or b.is_error():
        return True
    if is_numeric(a) and is_numeric(b):
        return True
    return is_assignable(a, b) or is_assignable(b, a)

#Regresa el tipo de la operacion

def result_of_arithmetic(op: str, a: Type, b: Type):
    if a.is_error() or b.is_error():
        return ERROR
    if op == "+" and a == STRING and b == STRING:
        return STRING
    if a == FLOAT or b == FLOAT:
        return FLOAT
    return INTEGER
