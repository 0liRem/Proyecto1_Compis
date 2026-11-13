// Recorrido por las características que traduce el compilador a MIPS
var contador: integer = 0;
const PI: float = 3.5;

function fact(n: integer): integer {
    if (n <= 1) { return 1; }
    return n * fact(n - 1);
}

function fib(n: integer): integer {
    if (n < 2) { return n; }
    return fib(n - 1) + fib(n - 2);
}

function externa(x: integer): integer {
    function interna(y: integer): integer {
        contador = contador + 1;
        return x * y;          // 'x' pertenece a la función externa
    }
    return interna(3) + interna(4);
}

class Animal {
    var nombre: string;
    var patas: integer;
    function constructor(n: string, p: integer) {
        this.nombre = n;
        this.patas = p;
    }
    function describir(): string {
        return this.nombre + " tiene patas";
    }
    function total(k: integer): integer {
        return this.patas * k;
    }
}

print(fact(6));
print(fib(10));
print(externa(5));
print(contador);

var a: Animal = new Animal("Perro", 4);
print(a.describir());
print(a.total(3));

var nums: integer[] = [5, 3, 8, 1];
var suma: integer = 0;
foreach (v in nums) { suma = suma + v; }
print(suma);
nums[2] = 100;
print(nums[2]);

var i: integer = 0;
while (i < 10) {
    i = i + 1;
    if (i == 3) { continue; }
    if (i == 6) { break; }
}
print(i);

for (var k: integer = 0; k < 3; k = k + 1) { print(k * k); }

switch (suma) {
    case 17: print("diecisiete"); break;
    default: print("otro");
}

var x: float = PI * 2;
print(x);
print(x > 6.5);
print(7 % 4);
print("a" + "b" == "ab");
print(i > 2 ? 111 : 222);
try { print("dentro del try"); } catch (e) { print("NO debe verse"); }
