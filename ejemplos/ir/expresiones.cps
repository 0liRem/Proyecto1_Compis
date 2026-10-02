// Demostración de reciclaje de temporales, floats, cortocircuito y arreglos
var a: integer = 1;
var b: integer = 2;
var c: integer = 3;
var d: integer = 4;
var e: integer = 5;
var r: integer = a + b * c - d / e;
var f: float = 2.5 + a;
var g: float = 3;
var ok: boolean = (a < b) && (c < d) || !(e == 1);
var arr: integer[] = [1, 2, 3];
arr[1] = r;
print(arr[1] + 1);
