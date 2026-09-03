# Analizador Léxico, Sintáctico y Semántico de Compiscript

Herramienta de escritorio que recibe un programa Compiscript
—ya sea desde un archivo `.cps` o escrito directamente en el editor—, y
realiza su análisis **léxico**, **sintáctico** y **semántico** usando un
lexer/parser generado con **ANTLR4** más un analizador semántico propio
escrito con el patrón *Visitor*. Muestra en una interfaz gráfica todos los
errores encontrados —con línea, columna, símbolo y una descripción clara
en español— sin detenerse en el primer error, y permite visualizar el
árbol sintáctico de forma gráfica.

El alcance es estrictamente léxico, sintáctico y semántico: **no** se
ejecuta el programa, ni se genera código intermedio ni código objeto.

---

## 1. Estructura del proyecto

```
CompiscriptAnalyzer/
├── grammar/
│   └── Compiscript.g4        # Gramática ANTLR4
├── src/
│   ├── generated/            # Lexer/Parser generados por ANTLR
│   ├── error_handling.py     # Listeners de error léxico/sintáctico + traducción a español + recuperación
│   ├── analyzer.py           # Orquesta las tres fases: léxica, sintáctica y semántica
│   ├── gui.py                # IDE (Tkinter + ttkbootstrap): editor, tabla de errores, árbol visual
│   └── semantic/             # Analizador semántico (ver sección 4)
│       ├── types.py          # Sistema de tipos y reglas de compatibilidad
│       ├── symbols.py        # Símbolos y tabla de símbolos con manejo de entornos
│       ├── errors.py         # Colección de errores semánticos (con deduplicación)
│       ├── checker.py        # Visitor principal: aplica todas las reglas semánticas
│       └── tree_view.py      # Exporta el árbol sintáctico como imagen (Graphviz)
├── ejemplos/
│   ├── correcto.cps          # Programa válido (léxica, sintáctica y semánticamente)
│   ├── con_errores.cps       # Programa con errores léxicos y sintácticos variados
│   └── semantica/
│       └── _smoke.cps        # Programa que dispara, a propósito, casi todas las reglas semánticas
├── tests/
│   ├── conftest.py           # Utilidades compartidas para los tests
│   └── test_semantic.py      # Batería de pruebas (pytest) de las reglas semánticas
├── main.py                   # Punto de entrada de la aplicación (IDE)
├── regenerar_parser.bat / .sh # Regenera Lexer/Parser desde la gramática (Windows / Linux-Mac)
├── requirements.txt
└── README.md
```

---

## 2. Instalación y ejecución

El proyecto **ya incluye** el lexer y el parser generados por ANTLR en
`src/generated/`, así que **no necesitas tener Java instalado** para usar
la aplicación tal como se entrega. Solo necesitas Python 3.9+ y dos
paquetes de Python. \
Se puede regenerar el ANTLR si algo falla

### Paso 1 — Instalar dependencias

```bash
cd Lab1
pip install -r requirements.txt
```

Para poder usar el botón **“Ver árbol sintáctico”** del IDE también se
necesita tener instalado el binario `dot` de **Graphviz** en el sistema
(no basta con el paquete de Python `graphviz`, que sólo es una interfaz
hacia ese binario):

- Ubuntu/Debian: `sudo apt install graphviz`
- macOS (Homebrew): `brew install graphviz`
- Windows: instalador desde <https://graphviz.org/download/> (agregar la
  carpeta `bin` al PATH) en la aplicacion de editar variables de entorno

Si Graphviz no está disponible, el resto del analizador (léxico, sintáctico
y semántico, incluida la tabla de errores) funciona igual; sólo la
visualización gráfica del árbol quedará deshabilitada.

### Paso 2 — Ejecutar la aplicación

```bash
python main.py
```

Se abrirá la ventana principal (el IDE). Desde ahí puedes:

- Escribir tu propio programa directamente en el editor (**“Nuevo”**),
  o abrir uno existente (**“Abrir .cps”**) — puedes probar con
  `ejemplos/correcto.cps` o `ejemplos/con_errores.cps`.
- Guardar tus cambios con **“Guardar”**.
- Hacer clic en **“Analizar”** para correr las tres fases (léxica,
  sintáctica y semántica) sobre el código del editor.
- Revisar la tabla de la derecha con todos los errores encontrados (o el
  mensaje de éxito si no hay ninguno). Puedes filtrar por tipo (Léxico /
  Sintáctico / Semántico) y hacer clic en una fila para saltar a esa línea
  en el editor, donde las líneas con errores quedan resaltadas.
- Hacer clic en **“Ver árbol sintáctico”** para abrir una ventana con la
  representación gráfica (Graphviz) del árbol de derivación del programa
  analizado.

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

## 4. Análisis semántico

### 4.1 Cambio en la gramática: soporte de `float`

Varias reglas semánticas pedidas explícitamente (verificación de tipos en
operaciones aritméticas sobre `integer`/`float`) requieren un tipo `float`
que la gramática original no tenía (sólo `boolean`, `integer`, `string`).
Se agregó de la forma mínima posible, manteniendo el resto de la gramática
intacta:

```antlr
baseType: 'boolean' | 'integer' | 'float' | 'string' | Identifier;
...
Literal
  : FloatLiteral
  | IntegerLiteral
  | StringLiteral
  ;
FloatLiteral: [0-9]+ '.' [0-9]+;
```

El Lexer/Parser en `src/generated/` ya están regenerados con este cambio
(con ANTLR 4.11.1; ver la nota de versión en `regenerar_parser.bat`/`.sh`).

### 4.2 Arquitectura

El análisis semántico vive por completo en `src/semantic/` y es
independiente del analizador léxico/sintáctico existente: recibe el árbol
ya construido por ANTLR y lo recorre una sola vez con el patrón **Visitor**
(`SemanticChecker`, en `checker.py`, extiende la clase `CompiscriptVisitor`
generada por ANTLR).

```
              analyzer.analizar_texto()
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   CompiscriptLexer  CompiscriptParser  SemanticChecker.analyze(árbol)
   (léxico)          (sintáctico)             │
                                               ▼
                                  types.py + symbols.py + errors.py
```

- **`types.py`** — Sistema de tipos: `integer`, `float`, `boolean`,
  `string`, `void`, `null`, tipos de arreglo (`T[]`), tipos de clase y
  tipos de función (para usar funciones/métodos como valores). Aquí viven
  las reglas de compatibilidad (`is_assignable`, `are_comparable`,
  `result_of_arithmetic`, jerarquías de clases). Incluye un tipo especial
  **`ERROR`** que actúa como "veneno": cualquier operación con un operando
  `ERROR` se da por válida y devuelve `ERROR`, en vez de generar un
  segundo error. Éste es el mecanismo central anti-cascada.

- **`symbols.py`** — Tabla de símbolos con manejo de entornos. Un `Scope`
  representa un entorno léxico (`global`, `function`, `block`, `class`,
  `loop`, `switch`) y los entornos forman un árbol mediante `parent`; esto
  es lo que resuelve el ámbito hacia afuera y da soporte natural a
  *closures*: una función anidada simplemente tiene como padre el entorno
  donde fue declarada, no el entorno global. `ClassSymbol` guarda
  atributos, métodos y constructor, con búsqueda que sube por la cadena de
  herencia (`find_field`, `find_method`, `find_constructor`).

- **`errors.py`** — `SemanticErrors` reutiliza `CompiscriptError` (la
  misma clase que usan los errores léxicos/sintácticos) con tipo
  `"Semántico"`, para que se listen en la misma tabla de la interfaz.
  Descarta duplicados exactos de (línea, columna, mensaje).

- **`checker.py`** — El Visitor. Antes de revisar el cuerpo de un bloque
  (el programa completo, un `{ ... }`, el cuerpo de una función o de una
  clase), se hace una **pre-declaración** (`_predeclare_block`): se
  registran los nombres de todas las clases y funciones de ese nivel
  *antes* de revisar ningún cuerpo. Esto es lo que permite:
  - **Recursión**: la función ya está en el entorno cuando se revisa su
    propio cuerpo.
  - **Referencias hacia adelante** entre funciones/clases hermanas
    (a → b y b → a, sin importar el orden en que se escribieron).
  - **Métodos de una clase llamándose entre sí** sin importar el orden.

- **`tree_view.py`** — Construye un `graphviz.Digraph` a partir del árbol
  de ANTLR (un nodo por regla, un nodo hoja por token) y lo renderiza a
  PNG/SVG. Se usa desde el IDE (`gui.py`) para el botón “Ver árbol
  sintáctico”.

### 4.3 Reglas semánticas implementadas


1. **Sistema de tipos**: aritmética (`+ - * /`) restringida a
   `integer`/`float` (con `+` admitiendo también `string`+`string` como
   concatenación, ya que así se usa en los ejemplos del curso —
   `this.nombre + " hace ruido."`); lógicos (`&& || !`) restringidos a
   `boolean`; comparaciones (`==`, `!=` con tipos compatibles;
   `< <= > >=` con operandos numéricos); asignaciones con
   ensanchamiento `integer → float` y polimorfismo de clases
   (subclase asignable a variable de la superclase); inicialización de
   constantes (la propia gramática ya obliga a `const x = valor;`, así
   que esto se refuerza sintácticamente); tipos de listas.
2. **Manejo de ámbito**: resolución de nombres por la cadena de entornos;
   error por variable/función no declarada; prohibición de redeclarar un
   identificador en el mismo entorno; cada bloque/función/clase abre su
   propio entorno.
3. **Funciones**: aridad y tipos de argumentos (coincidencia posicional);
   tipo de retorno; recursión; funciones anidadas/closures; funciones
   duplicadas (no hay sobrecarga).
4. **Control de flujo**: condiciones de `if/while/do-while/for` deben ser
   `boolean`; `break`/`continue` sólo dentro de un bucle (`break` también
   dentro de un `switch`); `return` sólo dentro de una función.
5. **Clases y objetos**: acceso a atributos/métodos existentes (incluidos
   heredados) vía `.`; validación de aridad/tipos del constructor (se
   hereda el de la superclase si la subclase no define uno propio); `this`
   sólo válido dentro de un método.
6. **Listas**: todos los elementos de un literal de lista deben tener un
   tipo compatible entre sí; el índice de `[]` debe ser `integer`.
7. **Generales**: detección de código muerto (una sola vez por bloque, no
   una por cada instrucción inalcanzable); expresiones sin sentido
   semántico (p. ej. multiplicar una función); declaraciones duplicadas de
   variables y de parámetros.

### 4.4 Anti-cascada, anti-repetición y anti-ciclos

- **Tipo veneno (`ERROR`)**: toda expresión mal tipada devuelve `ERROR` en
  vez de un tipo real. Cualquier operación posterior que reciba un
  operando `ERROR` se considera válida (no repite el error). Por ejemplo,
  `let z: integer = (w + 1) * 2;` con `w` no declarada produce **un único**
  error ("`w` no ha sido declarado"), no uno adicional por cada operación
  que la contiene.
- **Deduplicación exacta** en `SemanticErrors`: descarta (línea, columna,
  mensaje) repetidos.
- **Protección contra ciclos de herencia**: `class_is_subtype` y los
  métodos `find_field`/`find_method`/`find_constructor` de `ClassSymbol`
  usan un conjunto de "visitados" al recorrer la cadena de superclases,
  de forma que una herencia cíclica (`class A : B { } class B : A { }`)
  se reporta como error en vez de causar un bucle infinito.
- A nivel de aplicación, cualquier excepción inesperada durante el
  análisis semántico se captura en `analyzer.py` y se convierte en un
  único error controlado, para que nunca tumbe el IDE.

---
Referencias:
   [ANTLR4](https://github.com/antlr/antlr4) \
   [TTKbootstrap](https://github.com/antlr/antlr4) \
   [Tkinter](https://docs.python.org/3/library/tkinter.html) \
   [Graphviz](https://graphviz.org/) \
   Claude: Reorganización de codigo, estructuración del proyecto y gramatica de los errores (la parte que los tokens se lean en idioma humano) \
   ChatGPT: Reestructuración del readme.md \
   Gemini: Creación de los ejemplos semanticos 