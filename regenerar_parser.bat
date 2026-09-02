@echo off
REM ---------------------------------------------------------------------
REM regenerar_parser.bat
REM ---------------------------------------------------------------------
REM Regenera el Lexer y el Parser de Compiscript a partir de la gramatica
REM grammar\Compiscript.g4 usando ANTLR4, y coloca los archivos resultantes
REM en src\generated\.
REM
REM
REM Requisitos: Java (JRE 11 o superior) instalado y en el PATH.
REM ---------------------------------------------------------------------

where java >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: No se encontro Java. Instala un JRE 11+ y vuelve a intentar.
    exit /b 1
)

echo Instalando/actualizando antlr4-tools...
pip install --quiet --upgrade antlr4-tools

echo Generando Lexer y Parser (target: Python3) ...
if not exist src\generated mkdir src\generated
cd grammar
antlr4 -Dlanguage=Python3 -visitor -no-listener -o ..\src\generated Compiscript.g4
cd ..
type nul > src\generated\__init__.py

echo.
echo Listo. Los archivos generados se encuentran en src\generated\.
