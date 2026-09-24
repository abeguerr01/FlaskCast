@echo off
REM ============================================================
REM  Compilar FlaskCast para Windows (un solo .exe)
REM  Requiere: Python 3.x instalado y en el PATH
REM ============================================================
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python no esta en el PATH. Instalalo primero.
    pause
    exit /b 1
)

echo Instalando dependencias de compilacion...
pip install pyinstaller
REM Pillow es opcional: genera un icon.ico multitalia. Si falta, se usa un fallback sin ella.
pip install pillow >nul 2>nul

echo Compilando binario (FlaskCast.spec)...
python -m PyInstaller --noconfirm --clean --distpath bin FlaskCast.spec

if errorlevel 1 (
    echo [ERROR] La compilacion fallo.
    pause
    exit /b 1
)

echo.
echo OK. Binario generado en: bin\FlaskCast.exe
echo Coloca el .exe donde quieras; "data" se creara junto a el.
pause