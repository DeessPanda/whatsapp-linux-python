# WhatsApp Linux (Python & Qt6)

<div align="center">

[![Linux](https://img.shields.io/badge/Linux-supported-brightgreen?style=for-the-badge&logo=linux)](https://kernel.org)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://python.org)
[![Qt6](https://img.shields.io/badge/Qt6-PySide6-green?style=for-the-badge&logo=qt)](https://qt.io)
[![Wayland](https://img.shields.io/badge/Wayland-supported-purple?style=for-the-badge&logo=wayland)](https://wayland.freedesktop.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

</div>

A lightweight, responsive, native-feeling WhatsApp Web desktop client for Linux built with **Python**, **PySide6**, and **QtWebEngine**.

## Features
- **Low RAM & CPU Usage**: Optimized with aggressive caching limits, single-process trial flags, and automated V8 garbage collection (`window.gc()`) when minimized to system tray.
- **System Tray Integration**: Close to tray, unread badge counter in tooltip, desktop notifications.
- **144Hz Smooth Scrolling**: Hardware-accelerated rendering layers and smooth scroll optimizations.
- **Wayland & X11 Support**: Automatic native platform detection.
- **PipeWire Support**: Microphone and camera permissions auto-granted for voice/video notes.

## Installation / Running

### Option 1: AppImage (Recommended & Easiest)
No installation or dependencies required! Just make it executable and run:
```bash
chmod +x whatsapp-linux.AppImage
./whatsapp-linux.AppImage
```

### Option 2: Run from Source
1. Install Python 3.10+ and pip.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the client:
   ```bash
   python3 main.py
   ```

## License
MIT
