// ============================================================================
// COMPISCRIPT: EJEMPLO CON ERRORES - COBERTURA TOTAL DE REGLAS SEMÁNTICAS
// ============================================================================

// ----------------------------------------------------------------------------
// 1. SISTEMA DE TIPOS Y CONSTANTES
// ----------------------------------------------------------------------------
// const UNINITIALIZED_CONST: integer; // ERROR 1.1: Inicialización obligatoria de constantes (const)

function testSistemaTipos(): void {
    var i: integer = 10;
    var f: float = 2.5;
    var b: boolean = true;
    var s: string = "texto";

    // ERROR 1.2: Tipos en operaciones aritméticas (+, -, *, /) — operandos no válidos
    var errArith: integer = i + b;

    // ERROR 1.3: Tipos en operaciones lógicas (&&, ||, !) — operandos no son boolean
    var errLogic: boolean = b && i;

    // ERROR 1.4: Compatibilidad de tipos en comparaciones
    var errComp: boolean = (i == b);

    // ERROR 1.5: Verificación de tipos en asignaciones
    i = "cadena_no_permitida";
}

// ----------------------------------------------------------------------------
// 2. MANEJO DE ÁMBITO, REDECLARACIONES Y ACCESO
// ----------------------------------------------------------------------------
var globalVar: integer = 100;
var globalVar: string = "duplicado"; // ERROR 2.1: Prohibir redeclaración de identificadores en el mismo ámbito

function testAmbito(): void {
    var localVar: integer = 50;
    variableInexistente = 10; // ERROR 2.2: Error por uso de variables no declaradas
}

function testAccesoBloque(): void {
    // ERROR 2.3: Control de acceso incorrecto a variables en ámbitos locales/anidados distintos
    localVar = 100; 
}

// ----------------------------------------------------------------------------
// 3. FUNCIONES, PROCEDIMIENTOS Y PARÁMETROS
// ----------------------------------------------------------------------------
function funcionDuplicada(): void {}
function funcionDuplicada(x: integer): void {} // ERROR 3.1: Múltiples declaraciones de funciones con el mismo nombre

function suma(a: integer, b: integer): integer {
    // ERROR 3.2: Validación del tipo de retorno de la función
    return "no es un integer";
}

function testLlamadaFunciones(): void {
    // ERROR 3.3: Validación del número de argumentos
    suma(10);

    // ERROR 3.4: Validación del tipo de argumentos (coincidencia posicional)
    suma(10, "veinte");
}

// ----------------------------------------------------------------------------
// 4. CONTROL DE FLUJO Y CÓDIGO MUERTO
// ----------------------------------------------------------------------------
function testControlFlujo(): void {
    // ERROR 4.1: Condiciones en if, while, do-while, for deben ser tipo boolean
    if (12345) {
        var x: integer = 1;
    }

    while ("no_boolean") {
        var y: integer = 2;
    }

    do {
        var z: integer = 3;
    } while (99.9);

    for (var i: integer = 0; "cadena"; i = i + 1) {
        var w: integer = 4;
    }

    // ERROR 4.2: Validación de break y continue sólo dentro de bucles
    break;
    continue;

    // ERROR 4.3: Detección de código muerto (instrucciones inalcanzables tras return)
    return;
    var codigoMuerto: integer = 100; 
}

// ERROR 4.4: Validación de que return esté dentro del cuerpo de una función
return 50;

// ----------------------------------------------------------------------------
// 5. CLASES, OBJETOS Y THIS
// ----------------------------------------------------------------------------
class Vehiculo {
    var marca: string;

    function encender(): void {
        this.marca = "Toyota";
    }
}

function testClases(): void {
    var v: Vehiculo = new Vehiculo();

    // ERROR 5.1: Validación de existencia de atributos accedidos mediante . (dot notation)
    v.modelo = "Corolla";

    // ERROR 5.2: Validación de existencia de métodos accedidos mediante .
    v.frenar();

    // ERROR 5.3: Manejo de 'this' fuera de un método de clase
    this.marca = "Honda";
}

// ----------------------------------------------------------------------------
// 6. LISTAS Y ESTRUCTURAS DE DATOS
// ----------------------------------------------------------------------------
function testListas(): void {
    var listaEnteros: integer[] = [1, 2, 3];

    // ERROR 6.1: Verificación de tipo de elementos en asignación e inicialización de listas
    listaEnteros[0] = "texto_invalido";

    // ERROR 6.2: Validación de índices (el índice debe ser de tipo integer)
    var elemento: integer = listaEnteros["indice_cadena"];
}

// ----------------------------------------------------------------------------
// 7. GENERALES Y EXPRESIONES SIN SENTIDO SEMÁNTICO
// ----------------------------------------------------------------------------
function testExpresionesGenerales(): void {
    // ERROR 7.1: Expresiones sin sentido semántico (ej. multiplicar o sumar funciones)
    var expresionInvalida: integer = suma * 5;
}