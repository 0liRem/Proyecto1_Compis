#!/usr/bin/env bash
# ---------------------------------------------------------------------
# regenerar_parser.sh
# ---------------------------------------------------------------------
# Regenera el Lexer y el Parser de Compiscript a partir de la gramática
# grammar/Compiscript.g4 usando ANTLR4, y coloca los archivos resultantes
# en src/generated/.
#
# Requisitos: Java (JRE 11 o superior) instalado y en el PATH.
#
# ---------------------------------------------------------------------
set -e

if ! command -v java >/dev/null 2>&1; then
  echo "ERROR: No se encontró Java. Instala un JRE 11+ y vuelve a intentar."
  exit 1
fi

echo "Instalando/actualizando antlr4-tools..."
pip install --quiet --upgrade antlr4-tools

echo "Generando Lexer y Parser (target: Python3) ..."
mkdir -p src/generated
(cd grammar && antlr4 -Dlanguage=Python3 -visitor -no-listener -o ../src/generated Compiscript.g4)
touch src/generated/__init__.py

echo
echo "Listo. Los archivos generados se encuentran en src/generated/."
