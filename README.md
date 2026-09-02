# Analizador Léxico y Sintáctico de Compiscript

Herramienta de escritorio que recibe un archivo `.cps` (Compiscript), realiza
su análisis **léxico** y **sintáctico** usando un lexer/parser generado con
**ANTLR4**, y muestra en una interfaz gráfica todos los errores encontrados
—con línea, columna, símbolo y una descripción clara en español— sin
detenerse en el primer error.

No se realiza análisis semántico, ejecución, ni generación de código: el
alcance es estrictamente el análisis léxico y sintáctico.

---

## 1. Estructura del proyecto

```
CompiscriptAnalyzer/
├── grammar/
│   └── Compiscript.g4        # Gramática ANTLR4 
├── src/
│   ├── generated/            # Lexer/Parser generados por ANTLR 
│   ├── error_handling.py     # Listeners de error + traducción a español + recuperación
│   ├── analyzer.py           # Orquesta el análisis léxico y sintáctico
│   └── gui.py                # Interfaz gráfica (Tkinter + ttkbootstrap)
├── ejemplos/
│   ├── correcto.cps          # Programa válido de ejemplo
│   └── con_errores.cps       # Programa con errores léxicos y sintácticos variados
├── main.py                   # Punto de entrada de la aplicación
├── requirements.txt
└── README.md
```

---

## 2. Instalación y ejecución

El proyecto **ya incluye** el lexer y el parser generados por ANTLR en
`src/generated/`, así que **no necesitas tener Java instalado** para usar
la aplicación tal como se entrega. Solo necesitas Python 3.9+ y dos
paquetes de Python.

### Paso 1 — Instalar dependencias

```bash
cd Lab1
pip install -r requirements.txt
```

### Paso 2 — Ejecutar la aplicación

```bash
python main.py
```

Se abrirá la ventana principal. Desde ahí:

1. Haz clic en **“Seleccionar archivo .cps”** y elige tu archivo fuente
   (puedes probar con `ejemplos/correcto.cps` o `ejemplos/con_errores.cps`).
2. Haz clic en **“▶ Analizar”**.
3. A la derecha aparecerá la tabla con todos los errores encontrados (o el
   mensaje de éxito si no hay ninguno). Puedes filtrar por tipo (léxico /
   sintáctico) y hacer clic en una fila para saltar a esa línea en el
   editor, donde las líneas con errores quedan resaltadas.

---


## 3. Diseño del manejo y recuperación de errores

### 3.1 Errores léxicos

El lexer generado por ANTLR ya se recupera automáticamente: cuando
encuentra un carácter (o secuencia de caracteres) que no coincide con
ningún token válido, lo reporta como error y **continúa escaneando** desde
el siguiente carácter, sin detener el proceso. Esto se verificó
explícitamente con dos casos:

- **Carácter suelto no reconocido** (p. ej. `@`, `$`, `~`): se reporta un
  único error puntual y el escaneo continúa con total normalidad en el
  resto del archivo.
- **Cadena de texto sin comilla de cierre**: ANTLR agrupa todo el texto
  hasta el salto de línea en un solo error (no un error por cada
  carácter), y `error_handling.py` lo detecta y traduce a un mensaje
  específico: *"Cadena de texto no cerrada: falta la comilla doble (") de
  cierre..."*.

Todo esto se captura mediante `LexicalErrorListener` (en
`error_handling.py`), que en lugar de imprimir la traza interna de ANTLR,
acumula cada error como un objeto `CompiscriptError` con tipo, línea,
columna, lexema y descripción en español.

### 3.2 Errores sintácticos

Se usa una estrategia de recuperación en **modo pánico**, construida sobre
`DefaultErrorStrategy` de ANTLR:

- **Inserción/eliminación de un solo token**: para errores puntuales (p.
  ej. una coma faltante), el parser intenta primero insertar o eliminar
  un único token antes de recurrir a la sincronización completa.
- **Sincronización con el conjunto FOLLOW**: ante un error más grave, se
  descartan tokens del flujo de entrada hasta encontrar uno que
  pertenezca al conjunto de tokens válidos para continuar (por ejemplo,
  el `;` que cierra una sentencia o el `}` que cierra un bloque),
  retomando el análisis desde ahí.
- **Salvaguarda anti-ciclos** (`RecoveryErrorStrategy` en
  `error_handling.py`): si dos errores ocurren exactamente en la misma
  posición del flujo de tokens (señal de que la recuperación no logró
  avanzar), se fuerza el consumo de un token adicional. Esto garantiza
  que el análisis **siempre progresa** y termina, sin importar cuán
  malformado esté el archivo de entrada.

Cada error sintáctico se traduce desde el mensaje interno de ANTLR (en
inglés, con notación tipo `mismatched input ';' expecting {...}`) a una
oración clara en español, usando un diccionario de nombres amigables para
cada símbolo de la gramática (por ejemplo, `';'` → *"el punto y coma
';'"*, `Identifier` → *"un identificador (nombre de variable, función o
clase)"*).

### 3.3 Verificación

Con el archivo `ejemplos/con_errores.cps` (que contiene, a propósito: una
declaración sin `;`, una condición de `if` sin cerrar paréntesis, un
parámetro de función sin `:`, una lista con elementos mal separados, una
cadena sin cerrar, un carácter inválido `@` y un `switch` con `case` sin
`:`), el analizador reporta **10 errores en una sola ejecución** — 2
léxicos y 8 sintácticos — sin detenerse en el primero y sin entrar en
bucles infinitos.

Con `ejemplos/correcto.cps` (un programa válido según la gramática), el
analizador reporta: *"El archivo fue analizado correctamente. No se
encontraron errores léxicos ni sintácticos."*

---

## 4. Nota sobre la gramática y la especificación

Al probar el proyecto se observó una inconsistencia entre
`Definición de Compiscript.md` y `Compiscript.g4`: el documento muestra
ejemplos como

```cps
if (n < 60) continue;
if (n == 100) break;
```

es decir, sentencias `if`/`while` **sin llaves**. Sin embargo, la
gramática entregada define:

```antlr
ifStatement: 'if' '(' expression ')' block ('else' block)?;
whileStatement: 'while' '(' expression ')' block;
```

donde `block` siempre requiere `{` y `}`. Como la gramática es la fuente
de verdad para este analizador, `if (n < 60) continue;` (sin llaves) es
reportado como un **error sintáctico real** por esta herramienta. El
archivo `ejemplos/correcto.cps` ya usa llaves en todos los casos para
reflejar el comportamiento real de la gramática. Vale la pena confirmar
con el equipo del curso cuál de los dos documentos es el vigente antes de
la entrega final.

---

# Video

[![Video](https://youtu.be/82f048_YeWw)](https://youtu.be/82f048_YeWw)

Referencias:
   [ANTLR4](https://github.com/antlr/antlr4)
   [TTKbootstrap](https://github.com/antlr/antlr4)
   [Tkinter](https://docs.python.org/3/library/tkinter.html)
   Claude: Reorganización de codigo, estructuración del proyecto y gramatica de los errores (la parte que los tokens se lean en idioma humano)
   ChatGPT: Reestructuración del readme.md