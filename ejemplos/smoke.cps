// Smoke test rápido: mezcla de varias reglas semánticas
let a: integer = "hola";          // asignación incompatible
const PI = 3.14;                  // const sin problema
PI = 3.15;                        // reasignar constante -> error

function suma(x: integer, y: integer): integer {
  return x + y;
}
function suma(x: integer): integer { return x; } // función duplicada

let r: integer = suma(1, 2, 3);   // aridad incorrecta
let s: string = suma(1, 2);       // tipo de retorno incompatible con destino

while (5) { print("nope"); }      // condición no boolean

function f(): void {
  return 3;                       // return con valor en función void
}

class A {
  let x: integer;
  function metodo(): integer {
    return this.y;                // atributo inexistente
  }
}

function g(): integer {
  break;                          // break fuera de bucle
  return 1;
}

for (let i: integer = 0; i < 3; i = i + 1) {
  print(i);
  continue;
  print("inalcanzable");          // código muerto
}

let arr: integer[] = [1, 2, true]; // lista con tipos mezclados
print(arr["x"]);                   // índice no entero

let z = w + 1;                     // variable no declarada (no debe generar 2 errores)
