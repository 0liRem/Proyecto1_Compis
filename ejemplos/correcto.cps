
class Animal {
  let nombre: string;

  function constructor(nombre: string) {
    this.nombre = nombre;
  }

  function hablar(): string {
    return this.nombre + " hace ruido.";
  }
}

class Perro : Animal {
  function hablar(): string {
    return this.nombre + " ladra.";
  }
}

function factorial(n: integer): integer {
  if (n <= 1) {
    return 1;
  }
  return n * factorial(n - 1);
}

function main(): integer {
  let perro: Perro = new Perro("Toby");
  print(perro.hablar());

  let notas: integer[] = [90, 85, 100];
  let i: integer = 0;
  while (i < 3) {
    print(notas[i]);
    i = i + 1;
  }

  foreach (n in notas) {
    if (n < 60) { continue; }
    if (n == 100) { break; }
    print(n);
  }

  try {
    let peligro = notas[100];
  } catch (err) {
    print("Error atrapado: " + err);
  }

  return factorial(5);
}
