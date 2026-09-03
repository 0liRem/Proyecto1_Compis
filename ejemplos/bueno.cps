// ============================================================================
// COMPISCRIPT: EJEMPLO 100% CORRECTO - COBERTURA TOTAL DE REGLAS SEMÁNTICAS
// ============================================================================

// ----------------------------------------------------------------------------
// 1. MANEJO DE ÁMBITO Y TABLA DE SÍMBOLOS (Global, Funciones, Clases, Bloques)
// ----------------------------------------------------------------------------
var globalCounter: integer = 10;
var globalFactor: float = 1.5;
const MAX_LIMIT: integer = 100;
var flagGlobal: boolean = true;
var greeting: string = "Compiscript Valid";

// ----------------------------------------------------------------------------
// 2. CLASES, OBJETOS, CONSTRUCTOR, ATRIBUTOS, MÉTODOS Y 'THIS'
// ----------------------------------------------------------------------------
class Persona {
    var nombre: string;
    var edad: integer;

    function init(n: string, e: integer): void {
        this.nombre = n;
        this.edad = e;
    }

    function esMayorDeEdad(): boolean {
        return this.edad >= 18;
    }

    function getNombre(): string {
        return this.nombre;
    }
}

// ----------------------------------------------------------------------------
// 3. LISTAS Y ESTRUCTURAS DE DATOS (Tipo de Elementos e Índices)
// ----------------------------------------------------------------------------
var numeros: integer[] = [10, 20, 30, 40, 50];
var nombres: string[] = ["Ana", "Carlos", "Elena"];

function testListas(): integer {
    var idx: integer = 2;
    var val: integer = numeros[idx]; // Acceso a índice mediante expresión integer
    numeros[0] = 100;                 // Asignación con tipo coincidente
    return val;
}

// ----------------------------------------------------------------------------
// 4. FUNCIONES RECURSIVAS, ANIDADAS Y CLOSURES
// ----------------------------------------------------------------------------
function factorial(n: integer): integer {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1); // Llamada recursiva
}

function crearMultiplicador(factor: integer): integer {
    // Función anidada
    function multiplicar(val: integer): integer {
        return val * factor; // Captura variable 'factor' del entorno externo
    }
    var res: integer = multiplicar(10);
    return  res;
}

// ----------------------------------------------------------------------------
// 5. CONTROL DE FLUJO (if, while, do-while, for, switch, break, continue)
// ----------------------------------------------------------------------------
function testControlFlujo(opcion: integer): boolean {
    // Expresión booleana en if / else
    if (opcion > 0 && flagGlobal) {
        var bloqueVar: integer = 5; // Variable en bloque anidado
        globalCounter = globalCounter + bloqueVar;
    } else {
        globalCounter = 0;
    }

    // Bucle while con break y continue
    var i: integer = 0;
    while (i < 5) {
        if (i == 2) {
            i = i + 1;
            continue;
        }
        if (i == 4) {
            break;
        }
        i = i + 1;
    }

    // Bucle do-while
    var j: integer = 0;
    do {
        j = j + 1;
    } while (j < 3);

    // Bucle for
    for (var k: integer = 0; k < 5; k = k + 1) {
        globalCounter = globalCounter + k;
    }

    // Control de flujo con switch
    switch (opcion) {
        case 1:
            globalCounter = 10;
            break;
        case 2:
            globalCounter = 20;
            break;
        default:
            globalCounter = 0;
            break;
    }

    return true;
}

// ----------------------------------------------------------------------------
// 6. OPERACIONES ARITMÉTICAS, LÓGICAS Y COMPARACIONES
// ----------------------------------------------------------------------------
function testExpresiones(): void {
    var intVal: integer = 10 + 20 * 2 - 5 / 1;
    var floatVal: float = 2.5 + 3.14 * 1.0 / 0.5;
    var boolVal: boolean = (intVal > 5) && (floatVal <= 10.0) || (!flagGlobal);
    var compVal: boolean = (intVal == 35) && (greeting == "Compiscript Valid");

    // Instanciación y uso correcto del constructor
    var p: Persona = new Persona();
    p.init("Laura", 25);
    
    var esMayor: boolean = p.esMayorDeEdad();
    var n: string = p.getNombre();

    var ejecucionFlujo: boolean = testControlFlujo(1);
    var elementoLista: integer = testListas();
    var fact: integer = factorial(5);
    var closureMsg: integer = crearMultiplicador(3);
}

// Invocación general
testExpresiones();