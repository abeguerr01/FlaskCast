#!/usr/bin/env bash
# ============================================================
#  Compilar FlaskCast para Linux (un solo binario ELF)
#  Requiere: Python 3.x, pip y Tkinter en el sistema
#  Consejo: compila en la distro MAS ANTIGUA que quieras
#           soportar (el binario depende de la glibc del
#           sistema de compilación).
# ============================================================
set -e

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] python3 no está en el PATH."
    exit 1
fi

echo "Comprobando Tkinter (necesario para el panel de administración)..."
if ! python3 -c "import tkinter; import tkinter.filedialog; import tkinter.messagebox" >/dev/null 2>&1; then
    echo "[ERROR] Tkinter no está disponible en este Python."
    echo "  Debian/Ubuntu:  sudo apt install -y python3-tk"
    echo "  Fedora:         sudo dnf install -y python3-tkinter"
    echo "  Arch:           sudo pacman -S tk"
    exit 1
fi

echo "Creando el entorno virtual de compilación (.venv-build)..."
if ! python3 -m venv .venv-build >/dev/null 2>&1; then
    echo "[ERROR] No se pudo crear el entorno virtual."
    echo "  Debian/Ubuntu:  sudo apt install -y python3-venv"
    echo "  Fedora:         sudo dnf install -y python3-virtualenv"
    echo "  Arch:           sudo pacman -S python-virtualenv"
    exit 1
fi
# shellcheck disable=SC1091
source .venv-build/bin/activate

echo "Instalando dependencias de compilación..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pip install pyinstaller

echo "Compilando binario (FlaskCast.spec)..."
python3 -m PyInstaller --noconfirm --clean --distpath bin FlaskCast.spec

# Los binarios ELF no incorporan iconos; se crea un .desktop para el lanzador.
BIN_DIR="$(cd "$(dirname "$0")" && pwd)/bin"
LOGO_ABS="$BIN_DIR/logo.png"
cp -f static/logo.png "$LOGO_ABS"
cat > "$BIN_DIR/FlaskCast.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=FlaskCast
Comment=Servidor multimedia FlaskCast
Exec="$BIN_DIR/FlaskCast"
Icon=$LOGO_ABS
Terminal=true
Categories=AudioVideo;
EOF
echo ""
echo "OK. Binario generado en: bin/FlaskCast"
echo "Icono del lanzador: bin/FlaskCast.desktop (apunta a bin/logo.png)"
echo "Coloca el binario donde quieras; 'data' se creará junto a él."