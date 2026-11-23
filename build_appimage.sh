#!/bin/bash
set -e
PROJECT_DIR="/home/deesspanda/Personal Data/Projects/whatsapp-linux-python"
cd "$PROJECT_DIR"

echo "[1/5] Setting up virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv --system-site-packages
fi
source venv/bin/activate
pip install --upgrade pip pyinstaller PySide6

echo "[2/5] Running PyInstaller..."
pyinstaller --onedir --clean --noconfirm \
    --name whatsapp-linux \
    --add-data "resources:resources" \
    --hidden-import=PySide6.QtWebEngineCore \
    --hidden-import=PySide6.QtWebEngineWidgets \
    --hidden-import=PySide6.QtNetwork \
    main.py

echo "[3/5] Preparing AppDir structure..."
rm -rf AppDir
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps

# Copy PyInstaller bundle output into usr/bin/whatsapp-linux
cp -r dist/whatsapp-linux/* AppDir/usr/bin/

# Copy desktop file and icons
cp whatsapp-linux.desktop AppDir/whatsapp-linux.desktop
cp whatsapp-linux.desktop AppDir/usr/share/applications/whatsapp-linux.desktop
cp resources/icon.png AppDir/whatsapp-linux.png
cp resources/icon.png AppDir/usr/share/icons/hicolor/256x256/apps/whatsapp-linux.png

# Create AppRun
cat << 'EOF' > AppDir/AppRun
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export XDG_DATA_DIRS="${HERE}/usr/share:${XDG_DATA_DIRS:-/usr/share}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland;xcb}"
exec "${HERE}/usr/bin/whatsapp-linux/whatsapp-linux" "$@"
EOF
chmod +x AppDir/AppRun

echo "[4/5] Building AppImage with appimagetool..."
appimagetool AppDir whatsapp-linux.AppImage

echo "[5/5] Done! AppImage created successfully."
ls -lh whatsapp-linux.AppImage
