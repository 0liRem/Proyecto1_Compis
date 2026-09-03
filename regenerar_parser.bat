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
REM
REM Nota de versiones: este proyecto se generó y probó con ANTLR 4.11.1
REM (antlr4-python3-runtime==4.11.1 en requirements.txt). antlr4-tools
REM descarga la última version de ANTLR disponible, que puede no coincidir.
REM Si al regenerar el parser la aplicacion falla por incompatibilidad de
REM version, instala el runtime de Python que corresponda, por ejemplo:
REM   pip install antlr4-python3-runtime==^<version-usada-por-antlr4-tools^>
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
