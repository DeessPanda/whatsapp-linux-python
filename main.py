#!/usr/bin/env python3
"""
WhatsApp Linux - Native Qt6 / Chromium Desktop Client
Built with PySide6 & QtWebEngine for responsive, lightweight, fully-featured WhatsApp on Linux.
"""

import sys
import os
import json
import re
import warnings

# Silence Qt deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Force native Wayland on KDE Plasma
if os.environ.get("XDG_SESSION_TYPE") == "wayland":
    os.environ.setdefault("QT_QPA_PLATFORM", "wayland;xcb")

# Set PulseAudio / PipeWire properties before Qt starts
os.environ["PULSE_PROP_application.name"] = "WhatsApp"
os.environ["PULSE_PROP_application.icon_name"] = "whatsapp"
os.environ["PULSE_PROP_media.role"] = "communication"

# Chromium engine flags for 144Hz high-refresh rate, low RAM, and full GPU acceleration
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--disable-logging "
    "--disable-background-networking "
    "--disable-component-update "
    "--disable-gpu-shader-disk-cache "
    "--disable-frame-rate-limit "
    "--disable-site-isolation-trials "
    "--expose-gc "
    "--disk-cache-size=33554432 "
    "--media-cache-size=16777216 "
    "--enable-aggressive-domstorage-flushing "
    "--ozone-platform-hint=auto "
    "--enable-features=VaapiVideoDecoder,VaapiIgnoreDriverChecks,CanvasOopRasterization "
    "--enable-gpu-rasterization "
    "--enable-zero-copy "
    "--ignore-gpu-blocklist "
    "--js-flags=--max-old-space-size=384 "
    "--renderer-process-limit=2 "
)

from PySide6.QtCore import (
    QUrl, Qt, QObject, Slot, QByteArray, QStandardPaths, QTimer
)
from PySide6.QtGui import (
    QIcon, QAction, QKeySequence, QDesktopServices, QShortcut
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSystemTrayIcon, QMenu
)
from PySide6.QtNetwork import (
    QLocalServer, QLocalSocket
)
from PySide6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage, QWebEngineSettings,
    QWebEngineScript
)
from PySide6.QtWebEngineWidgets import (
    QWebEngineView
)

APP_NAME = "WhatsApp Linux"
APP_ID = "whatsapp-linux"
SOCKET_NAME = "whatsapp-linux-instance.sock"
CONFIG_DIR = os.path.expanduser("~/.config/whatsapp-linux")
STORAGE_DIR = os.path.join(CONFIG_DIR, "qt_profile")
CACHE_DIR = os.path.expanduser("~/.cache/whatsapp-linux")
WINDOW_STATE_FILE = os.path.join(CONFIG_DIR, "window-state.json")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(SCRIPT_DIR, "resources", "icon.png")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

# Custom CSS for 144Hz buttery smooth scrolling, hardware compositing, and promo removal
CUSTOM_CSS = """
/* GPU composited rendering layers for chat and message lists to prevent visual jump/jitter */
div[data-testid="conversation-panel-messages"],
#pane-side,
div[role="region"] > div[tabindex="0"] {
    will-change: transform, scroll-position !important;
    transform: translateZ(0) !important;
    contain: layout paint !important;
    overscroll-behavior-y: contain !important;
}

/* Subpixel anti-aliasing to prevent font recalculation layout shifts during fast scroll */
body, div, span {
    -webkit-font-smoothing: antialiased !important;
    text-rendering: optimizeLegibility !important;
}

/* Hide Mac Promos */
div[data-testid="intro_panel_v2_title_card"],
div:has(> div > span[data-testid="wa-square-icon"]) {
    display: none !important;
}
"""


def load_window_state():
    try:
        if os.path.exists(WINDOW_STATE_FILE):
            with open(WINDOW_STATE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"width": 1200, "height": 800, "x": None, "y": None, "maximized": False}


def save_window_state(state):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(WINDOW_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[WhatsApp] Failed to save window state: {e}", file=sys.stderr)


class WhatsAppWebPage(QWebEnginePage):
    """Custom WebEnginePage with auto-granted permissions, clean console, and external link handling."""

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.featurePermissionRequested.connect(self.on_feature_permission_requested)

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        # Silence Meta's internal web console chatter (CSP reports, passive listener notices, deprecation warnings)
        pass

    def on_feature_permission_requested(self, security_origin, feature):
        feat_name = str(feature).split(".")[-1]
        print(f"[WhatsApp] Permission granted: {feat_name}")
        # Auto-grant microphone, camera, notifications, clipboard, desktop capture
        self.setFeaturePermission(
            security_origin,
            feature,
            QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
        )

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        host = url.host().lower()
        # Allow internal navigation within WhatsApp Web
        if not host or host.endswith("whatsapp.com") or host.endswith("whatsapp.net"):
            return True

        # Open external links in user's default web browser
        print(f"[WhatsApp] Opening external link in browser: {url.toString()}")
        QDesktopServices.openUrl(url)
        return False

    def createWindow(self, window_type):
        """Intercept popup windows (external links) and open in default browser."""
        class ExternalLinkInterceptor(QWebEnginePage):
            def acceptNavigationRequest(self, url, nav_type, is_main_frame):
                QDesktopServices.openUrl(url)
                return False

        return ExternalLinkInterceptor(self.profile(), self)


class WhatsAppMainWindow(QMainWindow):
    def __init__(self, profile):
        super().__init__()
        self.profile = profile
        self.is_quitting = False
        self.muted = False
        self.devtools_window = None

        self.setWindowTitle("WhatsApp")
        if os.path.exists(ICON_PATH):
            self.app_icon = QIcon(ICON_PATH)
            self.setWindowIcon(self.app_icon)
        else:
            self.app_icon = QIcon()

        # Webview setup
        self.view = QWebEngineView(self)
        self.page = WhatsAppWebPage(self.profile, self.view)
        self.view.setPage(self.page)
        self.setCentralWidget(self.view)

        # Settings
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, False)
        # Disable sluggish 60Hz software scroll interpolator so 144Hz displays get raw high-refresh scroll events
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, False)

        # Page signals
        self.page.titleChanged.connect(self.on_title_changed)

        # Keyboard shortcuts (F12 or Ctrl+Shift+I for DevTools)
        shortcut_f12 = QShortcut(QKeySequence("F12"), self)
        shortcut_f12.activated.connect(self.toggle_devtools)
        shortcut_inspect = QShortcut(QKeySequence("Ctrl+Shift+I"), self)
        shortcut_inspect.activated.connect(self.toggle_devtools)

        # System tray setup
        self.setup_tray()

        # Restore window state
        self.restore_state()

        # Load WhatsApp Web
        print("[WhatsApp] Loading https://web.whatsapp.com ...")
        self.view.load(QUrl("https://web.whatsapp.com"))

    def setup_tray(self):
        self.tray = QSystemTrayIcon(self.app_icon, self)
        self.tray.setToolTip("WhatsApp")

        menu = QMenu(self)

        open_action = QAction("Open WhatsApp", self)
        open_action.triggered.connect(self.show_and_activate)
        menu.addAction(open_action)

        devtools_action = QAction("Inspect Element (DevTools)", self)
        devtools_action.triggered.connect(self.toggle_devtools)
        menu.addAction(devtools_action)

        self.mute_action = QAction("Mute Notifications", self)
        self.mute_action.setCheckable(True)
        self.mute_action.triggered.connect(self.toggle_mute)
        menu.addAction(self.mute_action)

        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible() and not self.isMinimized() and self.isActiveWindow():
                self.hide()
            else:
                self.show_and_activate()

    def show_and_activate(self):
        self.show()
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def toggle_mute(self, checked):
        self.muted = checked
        print(f"[WhatsApp] Notifications muted: {self.muted}")

    def on_title_changed(self, title):
        self.setWindowTitle(title)
        # Parse unread count from "(N) WhatsApp"
        match = re.search(r"^\((\d+)\)", title)
        if match:
            count = match.group(1)
            self.tray.setToolTip(f"WhatsApp ({count})")
        else:
            self.tray.setToolTip("WhatsApp")

    def handle_notification(self, notification):
        if self.muted:
            print(f"[WhatsApp] Notification silenced (muted): {notification.title()}")
            return

        print(f"[WhatsApp] Desktop Notification: {notification.title()} - {notification.message()}")
        if self.tray.isVisible():
            self.tray.showMessage(
                notification.title(),
                notification.message(),
                self.app_icon,
                5000
            )

    def toggle_devtools(self):
        if self.devtools_window is None:
            self.devtools_window = QMainWindow(self)
            self.devtools_window.setWindowTitle("WhatsApp DevTools")
            devtools_view = QWebEngineView(self.devtools_window)
            self.page.setDevToolsPage(devtools_view.page())
            self.devtools_window.setCentralWidget(devtools_view)
            self.devtools_window.resize(900, 600)

        if self.devtools_window.isVisible():
            self.devtools_window.hide()
        else:
            self.devtools_window.show()
            self.devtools_window.raise_()
            self.devtools_window.activateWindow()

    def restore_state(self):
        state = load_window_state()
        self.resize(state.get("width", 1200), state.get("height", 800))
        if state.get("x") is not None and state.get("y") is not None:
            self.move(state["x"], state["y"])
        if state.get("maximized", False):
            self.showMaximized()
        else:
            self.show()

    def save_state(self):
        state = {
            "width": self.width(),
            "height": self.height(),
            "x": self.x(),
            "y": self.y(),
            "maximized": self.isMaximized(),
        }
        save_window_state(state)

    def closeEvent(self, event):
        if not self.is_quitting:
            event.ignore()
            self.save_state()
            self.hide()
            self.page.runJavaScript(
                "document.querySelectorAll('video, audio').forEach(el => el.pause()); if (window.gc) window.gc();"
            )
            print("[WhatsApp] Window hidden to system tray (paused media & garbage collected).")
        else:
            self.save_state()
            event.accept()

    def quit_app(self):
        self.is_quitting = True
        self.save_state()
        if self.devtools_window:
            self.devtools_window.close()
        QApplication.quit()


def setup_single_instance(window):
    """Enforce a single running instance via QLocalServer / QLocalSocket."""
    socket = QLocalSocket()
    socket.connectToServer(SOCKET_NAME)
    if socket.waitForConnected(500):
        print("[WhatsApp] Another instance is already running. Focusing existing window.")
        socket.write(b"focus\n")
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        sys.exit(0)

    # Server setup for current primary instance
    server = QLocalServer()
    QLocalServer.removeServer(SOCKET_NAME)
    if not server.listen(SOCKET_NAME):
        print(f"[WhatsApp] Warning: could not bind single instance server: {server.errorString()}", file=sys.stderr)

    def on_new_connection():
        sock = server.nextPendingConnection()
        if sock:
            sock.waitForReadyRead(500)
            data = sock.readAll().data().decode("utf-8", errors="ignore")
            if "focus" in data:
                window.show_and_activate()
            sock.disconnectFromServer()

    server.newConnection.connect(on_new_connection)
    return server


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName("WhatsApp")
    app.setDesktopFileName("whatsapp-linux")
    app.setQuitOnLastWindowClosed(False)

    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    # Configure persistent Chromium profile
    os.makedirs(STORAGE_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    profile = QWebEngineProfile(APP_ID, app)
    profile.setPersistentStoragePath(STORAGE_DIR)
    profile.setCachePath(CACHE_DIR)
    profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
    profile.setHttpUserAgent(USER_AGENT)

    # Inject CSS user script to remove "Download for Mac" title card cleanly
    user_script = QWebEngineScript()
    user_script.setName("mac_promo_cleaner")
    user_script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
    user_script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    css_js = f"""
    (function() {{
        try {{
            if (navigator.storage && navigator.storage.persist) {{
                navigator.storage.persist = () => Promise.resolve(true);
            }}
            const style = document.createElement('style');
            style.textContent = `{CUSTOM_CSS}`;
            (document.head || document.documentElement).appendChild(style);
        }} catch(e) {{}}
    }})();
    """
    user_script.setSourceCode(css_js)
    profile.scripts().insert(user_script)

    # Create main window
    window = WhatsAppMainWindow(profile)

    # Notification presenter
    profile.setNotificationPresenter(window.handle_notification)

    # Single instance guard
    _server = setup_single_instance(window)

    # Handle Ctrl+C (SIGINT) cleanly
    import signal
    signal.signal(signal.SIGINT, lambda *args: QApplication.quit())
    sig_timer = QTimer()
    sig_timer.start(300)
    sig_timer.timeout.connect(lambda: None)

    print("[WhatsApp] Native Qt6 WhatsApp Linux started successfully.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
