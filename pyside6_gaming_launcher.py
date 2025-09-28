#!/usr/bin/env python3
"""
Tibia Gaming Launcher - PySide6 Version

A modern gaming-style launcher with PySide6 Qt framework
that automatically updates Tibia from GitHub.
"""

import sys
import os
import time
import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QTextEdit, QComboBox, QFrame, QFileDialog, QMessageBox, QDialog, QGroupBox, QGraphicsDropShadowEffect, QListView,
    QAbstractButton, QLineEdit, QAbstractItemView, QSlider, QScrollBar, QSpinBox, QDoubleSpinBox, QCheckBox, QRadioButton,
    QProgressDialog
)
def shadow(radius=32, color=(0, 0, 0, 160), offset=(0, 12)):
    eff = QGraphicsDropShadowEffect()
    eff.setBlurRadius(radius)
    from PySide6.QtGui import QColor
    eff.setColor(QColor(*color))
    eff.setOffset(*offset)
    return eff
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QPropertyAnimation, QEasingCurve, QObject
from PySide6.QtGui import QPixmap, QFont, QPalette, QColor, QIcon, QBrush, QPainter, QPen, QPainterPath

try:
    # Prefer packaged path
    from tibialauncher.core.launcher_core import LauncherCore
except Exception:
    # Fallback for dev if package path not available
    from launcher_core import LauncherCore


def resource_path(*parts: str) -> str:
    """Return absolute path to resource (works for PyInstaller bundle and dev).

    When frozen by PyInstaller, sys._MEIPASS points to the temp extraction dir.
    Otherwise use the current file's parent directory.
    """
    base = getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)
    return str(Path(base, *parts))

class CenteredComboBox(QComboBox):
    """QComboBox with centered display & popup text.

    Keeps default drop-down arrow visible (previous version hid it which confused users),
    while centering both the line edit / display text and the popup entries.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        view = QListView()
        # Center text inside popup list
        view.setStyleSheet("QListView { text-align: center; }")
        self.setView(view)
        self.setInsertPolicy(QComboBox.NoInsert)
        # Ensure the width adapts nicely to content without truncation
        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)

    def addItems(self, items):  # type: ignore[override]
        super().addItems(items)
        for i in range(self.count()):
            self.setItemData(i, Qt.AlignCenter, Qt.TextAlignmentRole)


class DragContainer(QWidget):
    """Central container that lets user drag the frameless window from anywhere
    that is not an interactive control (buttons, inputs, lists, etc.)."""

    def __init__(self, window: QMainWindow):
        super().__init__(parent=window)
        self._window = window
        self._dragging = False
        self._drag_offset = None
        # Preload background artwork for full-frame paint
        try:
            bg_path = resource_path('images', 'background-artwork.png')
            self._bg_pix = QPixmap(bg_path) if os.path.exists(bg_path) else None
            self._bg_scaled = None
        except Exception:
            self._bg_pix = None
            self._bg_scaled = None

    def _is_interactive(self, w: QWidget) -> bool:
        return isinstance(
            w,
            (
                QAbstractButton,
                QComboBox,
                QLineEdit,
                QTextEdit,
                QAbstractItemView,
                QSlider,
                QScrollBar,
                QSpinBox,
                QDoubleSpinBox,
                QCheckBox,
                QRadioButton,
                QProgressBar,
            ),
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.pos())
            if child is None or not self._is_interactive(child):
                gp = event.globalPosition() if hasattr(event, 'globalPosition') else event.globalPos()
                gp = gp.toPoint() if hasattr(gp, 'toPoint') else gp
                self._drag_offset = gp - self._window.frameGeometry().topLeft()
                self._dragging = True
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and (event.buttons() & Qt.LeftButton):
            gp = event.globalPosition() if hasattr(event, 'globalPosition') else event.globalPos()
            gp = gp.toPoint() if hasattr(gp, 'toPoint') else gp
            self._window.move(gp - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        # Keep a scaled version of the background matching current size
        if getattr(self, '_bg_pix', None) and not self._bg_pix.isNull():
            self._bg_scaled = self._bg_pix.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        super().resizeEvent(event)

    def paintEvent(self, event):
        # Paint a scaled background image clipped to rounded corners to fully fill the frame
        if getattr(self, '_bg_scaled', None) and not self._bg_scaled.isNull():
            try:
                painter = QPainter(self)
                painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
                # Clip to rounded rect (match stylesheet corner radius)
                path = QPainterPath()
                rect = self.rect()
                path.addRoundedRect(rect.adjusted(0, 0, -1, -1), 16, 16)
                painter.setClipPath(path)
                # Center the expanded pixmap
                x = (rect.width() - self._bg_scaled.width()) // 2
                y = (rect.height() - self._bg_scaled.height()) // 2
                painter.drawPixmap(x, y, self._bg_scaled)
                painter.end()
            except Exception:
                pass
        # Continue normal painting (children/widgets)
        super().paintEvent(event)


class VisualOverlay(QWidget):
    """Futuristic animated overlay: subtle scanlines + moving glow sweep.

    Transparent to mouse events; paints lightweight effects for a high-tech feel.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.phase = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(60)  # ~16 FPS would be 60ms for subtle motion

    def _tick(self):
        self.phase = (self.phase + 1) % 12
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        # Clip to rounded content area (match root radius and margins)
        path = QPainterPath()
        clip_rect = self.rect().adjusted(12, 12, -12, -12)
        path.addRoundedRect(clip_rect, 16, 16)
        painter.setClipPath(path)

        w = self.width()
        h = self.height()

        # 1) Horizontal scanlines (very subtle)
        line_color = QColor(0, 234, 255, 22)
        pen = QPen(line_color)
        pen.setWidth(1)
        painter.setPen(pen)
        spacing = 6
        offset = self.phase % spacing
        y = offset
        while y < h:
            painter.drawLine(0, y, w, y)
            y += spacing

        # 2) Diagonal light sweep (soft translucent band)
        sweep_color = QColor(255, 0, 204, 18)
        painter.setPen(Qt.NoPen)
        painter.setBrush(sweep_color)
        band_width = int(w * 0.2)
        x = (self.phase * 12) % (w + band_width) - band_width
        painter.drawRect(x, 0, band_width, h)
        painter.end()


class TitleBar(QFrame):
    """Custom frameless window title bar with drag support and window controls."""
    def __init__(self, window: QMainWindow):
        super().__init__(window)
        self.window = window
        self.setObjectName("title_bar")
        self.setFixedHeight(36)
        self._drag_pos = None

        h = QHBoxLayout(self)
        h.setContentsMargins(12, 4, 8, 4)
        h.setSpacing(8)

        # Icon + title
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(22, 22)
        icon_path = resource_path('images', 'logo-universal.png')
        if os.path.exists(icon_path):
            self.icon_label.setPixmap(QPixmap(icon_path).scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        h.addWidget(self.icon_label)

        self.title_label = QLabel("Tibia Launcher")
        self.title_label.setObjectName("window_title")
        h.addWidget(self.title_label)

        h.addStretch(1)

        # Window buttons (minimize, close)
        self.min_btn = QPushButton("–", objectName="win_btn")
        self.min_btn.setFixedSize(28, 24)
        self.min_btn.clicked.connect(self.window.showMinimized)
        h.addWidget(self.min_btn)

        self.close_btn = QPushButton("✕", objectName="win_btn_close")
        self.close_btn.setFixedSize(28, 24)
        self.close_btn.clicked.connect(self.window.close)
        h.addWidget(self.close_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # globalPosition() for Qt6 returns QPointF
            gp = event.globalPosition() if hasattr(event, 'globalPosition') else event.globalPos()
            gp = gp.toPoint() if hasattr(gp, 'toPoint') else gp
            self._drag_pos = gp - self.window.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            gp = event.globalPosition() if hasattr(event, 'globalPosition') else event.globalPos()
            gp = gp.toPoint() if hasattr(gp, 'toPoint') else gp
            self.window.move(gp - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class DownloadThread(QThread):
    """Thread for handling downloads without blocking UI"""
    progress_updated = Signal(float)
    status_updated = Signal(str)
    download_completed = Signal(bool)
    
    def __init__(self, launcher_core, download_type="update", minimap_type=None):
        super().__init__()
        self.launcher_core = launcher_core
        self.download_type = download_type
        self.minimap_type = minimap_type
    
    def run(self):
        """Run the download in background thread"""
        try:
            if self.download_type == "update":
                # Progress callback for updates
                def progress_callback(downloaded, total):
                    if total > 0:
                        progress = (downloaded / total) * 100
                        print(f"Download progress: {downloaded}/{total} = {progress:.1f}%")  # Debug print
                        self.progress_updated.emit(progress)
                        self.status_updated.emit(f"⬇️ Downloading: {progress:.1f}%")
                
                success = self.launcher_core.download_and_install(progress_callback)
                self.download_completed.emit(success)
                
            elif self.download_type == "minimap":
                # Minimap download logic here
                import requests
                import zipfile
                import shutil
                import tempfile
                
                minimap_urls = {
                    'with-markers': 'https://tibiamaps.io/downloads/minimap-with-markers',
                    'without-markers': 'https://tibiamaps.io/downloads/minimap-without-markers', 
                    'with-grid-overlay-and-poi-markers': 'https://tibiamaps.io/downloads/minimap-with-grid-overlay-and-poi-markers'
                }
                
                if self.minimap_type not in minimap_urls:
                    self.download_completed.emit(False)
                    return
                
                self.status_updated.emit(f"🗺️ Downloading {self.minimap_type} minimap...")
                
                # Download the minimap
                url = minimap_urls[self.minimap_type]
                response = requests.get(url, stream=True)
                response.raise_for_status()
                
                # Create temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            tmp_file.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                self.progress_updated.emit(progress)
                                self.status_updated.emit(f"🗺️ Downloading: {progress:.1f}%")
                    
                    temp_file_path = tmp_file.name
                
                # Extract and replace minimap folder
                minimap_dir = os.path.join(self.launcher_core.tibia_dir, "Tibia", "minimap")
                
                # Backup existing minimap if it exists
                if os.path.exists(minimap_dir):
                    backup_dir = f"{minimap_dir}_backup_{int(time.time())}"
                    shutil.move(minimap_dir, backup_dir)
                
                # Extract new minimap
                self.status_updated.emit("📂 Extracting minimap...")
                
                with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
                    zip_ref.extractall(os.path.join(self.launcher_core.tibia_dir, "Tibia"))
                
                # Clean up temp file
                os.unlink(temp_file_path)
                
                self.download_completed.emit(True)
                
        except Exception as e:
            self.status_updated.emit(f"❌ Download failed: {str(e)}")
            self.download_completed.emit(False)


class PySide6GamingLauncher(QMainWindow):
    # Signal for update notification
    update_available_signal = Signal(str, str)  # current_version, latest_version
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tibia Launcher")
        self.setFixedSize(700, 600)
        # Frameless window
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        # Rounded corners / translucent background
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # Initialize launcher core
        self.launcher_core = LauncherCore()
        # Launcher version (used for self-update checks and UI)
        try:
            self.LAUNCHER_VERSION = self.launcher_core.get_current_launcher_version()
        except Exception:
            self.LAUNCHER_VERSION = "1.0.0"
        
        # Set up the UI
        self.setup_ui()
        
        # Apply styling
        self.apply_styles()
        
        # Load background and logo
        self.load_images()

        # Animated overlay removed per request (no scanlines/sweep)
        
        # If first run, auto-set install directory to %APPDATA%/Tibia
        if getattr(self.launcher_core, 'first_run', False):
            try:
                target = os.path.join(os.path.expandvars(r"%APPDATA%"), "Tibia")
                os.makedirs(target, exist_ok=True)
                self.launcher_core.set_tibia_directory(target)
                self.log_message(f"📁 Installation directory set to %APPDATA% location: {target}")
            except Exception as e:
                self.log_message(f"⚠️ Failed to set default install directory: {e}")
        # Connect update signal
        self.update_available_signal.connect(self.show_update_prompt)
        
        # Initialize with automatic update check (after potential directory change)
        QTimer.singleShot(2000, lambda: self.check_for_updates(silent=False))  # Check after 2 seconds

        # Add fade-in animation
        self.setup_animations()
        # Neon glow animation removed per request (static shadow only)

        # Check for launcher updates in background (non-blocking)
        threading.Thread(target=self.check_launcher_update, daemon=True).start()

        # Set up periodic automatic update checking (every 2 hours)
        self.setup_periodic_update_check()

        # Launcher updates now use main window progress bar (no separate dialog needed)
    
    def setup_ui(self):
        """Set up the main user interface in Lionot card style"""
        central_widget = DragContainer(self)
        central_widget.setObjectName("window_root")
        # Ensure stylesheet background (image/color) is painted on translucent window
        central_widget.setAttribute(Qt.WA_StyledBackground, True)
        central_widget.setAutoFillBackground(True)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(18)
        # Custom Title Bar (frameless controls)
        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)
        # Title/logo row with image logo
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignHCenter)
        self.logo_label.setMinimumHeight(90)
        main_layout.addWidget(self.logo_label)

        # Card (central panel)
        card = QFrame(objectName="card")
        card.setGraphicsEffect(shadow(48, (0,0,0,190), (0,18)))
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(18)

        # Large progress bar area (replaces previous banner)
        self.progress_bar = QProgressBar(objectName="progress_bar")
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(28)
        self.progress_bar.setFormat("%p%")
        card_layout.addWidget(self.progress_bar)

        # Config + Minimap row
        top_controls = QHBoxLayout()
        top_controls.setSpacing(20)
        self.config_btn = QPushButton("⚙️ Config", objectName="config_btn")
        self.config_btn.clicked.connect(self.open_config_dialog)
        top_controls.addWidget(self.config_btn)
        # Increase left stretch so combo shifts right
        top_controls.addStretch(3)
        self.minimap_combo = CenteredComboBox(objectName="minimap_combo")
        # Populate choices
        self.minimap_combo.addItems([
            "Select Minimap...",  # index 0 sentinel
            "With Markers",
            "Without Markers",
            "With Grid & POI"
        ])
        self.minimap_combo.currentIndexChanged.connect(self.on_minimap_index_changed)
        top_controls.addWidget(self.minimap_combo, 0, Qt.AlignCenter)
        # Slightly smaller right stretch for asymmetry centering under logo
        top_controls.addStretch(2)
        self.download_minimap_btn = QPushButton("Download Minimap", objectName="download_minimap_btn")
        self.download_minimap_btn.setEnabled(False)
        self.download_minimap_btn.clicked.connect(self.download_selected_minimap)
        top_controls.addWidget(self.download_minimap_btn)
        card_layout.addLayout(top_controls)

        # Main action row: PLAY button
        action_row = QHBoxLayout()
        action_row.setSpacing(32)
        action_row.setContentsMargins(0, 10, 0, 0)

        # Play button (centered - automatic updates handle everything else)
        self.play_btn = QPushButton("PLAY", objectName="play_btn")
        # Static soft shadow for play button (no animation)
        self.play_glow = shadow(26, (0, 200, 255, 160), (0, 10))
        self.play_btn.setGraphicsEffect(self.play_glow)
        self.play_btn.clicked.connect(self.launch_tibia)
        self.play_btn.setMinimumHeight(72)
        self.play_btn.setMinimumWidth(200)
        action_row.addWidget(self.play_btn, 1, Qt.AlignHCenter)

        card_layout.addLayout(action_row)

        # Status below buttons
        self.status_label = QLabel("🟢 Ready", objectName="status")
        self.status_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.status_label)

        # Log section (full width, bottom)
        self.log_text = QTextEdit(objectName="log_text")
        self.log_text.setMaximumHeight(100)
        self.log_text.setReadOnly(True)
        card_layout.addWidget(self.log_text)

        main_layout.addWidget(card, 1)

        # Status bar (bottom)
        status_bar = QHBoxLayout()
        status_bar.setContentsMargins(4, 8, 4, 0)
        self.version_label = QLabel(f"v{self.LAUNCHER_VERSION}", objectName="muted")
        self.connection_label = QLabel("● Online", objectName="status")
        self.connection_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        status_bar.addWidget(self.version_label, 1)
        status_bar.addWidget(self.connection_label, 1, Qt.AlignRight)
        main_layout.addLayout(status_bar)

        # Initialize log
        self.log_message("🎮 Welcome to Tibia Launcher!")
        self.log_message("✨ Modern Qt interface loaded successfully")
        self.log_message("🔄 Automatic update checking will start in 2 seconds...")
    
    def apply_styles(self):
        """Apply a high-tech Qt Style Sheet for a modern neon look.

        Inject absolute path to background so it resolves inside PyInstaller bundle.
        """
        bg_path = resource_path('images', 'background-artwork.png').replace('\\', '/')
        style = """
QMainWindow {
    background-color: transparent;
    color: #e9f3fb;
    font-family: Segoe UI, Inter, Arial;
}
QWidget#window_root {
    background-color: #0e1116;
    background-image: url({BG_PATH});
    background-position: center center;
    background-repeat: no-repeat;
    border-radius: 16px;
}
QFrame#title_bar {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0b1219, stop:1 #101a23);
    border: 1px solid rgba(0,234,255,40);
    border-radius: 12px;
}
QLabel#window_title {
    color: #b7dffa;
    font-weight: 700;
    letter-spacing: 0.5px;
}
QPushButton#win_btn, QPushButton#win_btn_close {
    background: #0f1720;
    color: #d6f7ff;
    border: 1px solid rgba(0,234,255,60);
    border-radius: 6px;
}
QPushButton#win_btn:hover { background: #122333; }
QPushButton#win_btn_close:hover { background: #2b1a22; border-color: #ff4d4d; color: #fff; }
QFrame#card {
    background: rgba(18,20,27,180);
    border-radius: 22px;
    border: 1px solid rgba(0,234,255,40);
}
QPushButton#config_btn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #334155, stop:1 #3b485d);
    color: #e6eef6;
    border: 1px solid #475569;
    border-radius: 10px;
    padding: 8px 18px;
    font-weight: 600;
}
QPushButton#config_btn:hover { border-color: #00eaff; color: #ffffff; }
QPushButton#config_btn:pressed { background: #2a3444; }
QPushButton#download_minimap_btn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00eaff, stop:1 #4af3ff);
    color: #0b1014;
    border: 1px solid rgba(0,234,255,120);
    border-radius: 12px;
    padding: 10px 22px;
    font-weight: 700;
    letter-spacing: 0.5px;
}
QPushButton#download_minimap_btn:hover { border-color: #7ff7ff; }
QPushButton#download_minimap_btn:pressed { background: #00cfe6; }
QPushButton#download_minimap_btn:disabled { background: #3a3f44; border-color: #3a3f44; color: #7f868c; }
QPushButton#play_btn {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #00eaff, stop:1 #09ffc9);
    color: #061017;
    border: 1px solid rgba(9,255,201,140);
    border-radius: 16px;
    padding: 14px 32px;
    font-weight: 900;
    font-size: 32px;
    letter-spacing: 1.2px;
}
QPushButton#play_btn:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #28fff1, stop:1 #4dffd7); }
QPushButton#play_btn:pressed { padding-top: 15px; padding-bottom: 13px; }
QComboBox#minimap_combo {
    background: #0f1722;
    color: #d7f9ff;
    border: 1px solid rgba(0,234,255,60);
    padding: 6px 32px 6px 16px;
    border-radius: 10px;
    min-width: 190px;
    text-align: center;
}
QComboBox#minimap_combo:hover { border-color: rgba(0,234,255,120); }
QComboBox#minimap_combo::drop-down { width: 24px; border: none; }
QComboBox#minimap_combo::down-arrow {
    image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAKCAYAAABbayygAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAVUlEQVR4nGNgQAP/GBgY/jMwMDCgYGB4x4AFiNXAwPCfAQb+M2BgYHhPAlEM2B8gfgxEHWAAZiAmQMQPxiEgawZkgHEg2BnQAUxvA/E6IYwBxGBoYFQmAABf3Q+0PsL6QgAAAABJRU5ErkJggg==);
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 14px;
    height: 10px;
    margin-right: 8px;
}
QComboBox#minimap_combo QAbstractItemView {
    background: #0b1016;
    color: #dbfaff;
    selection-background-color: #133f55;
    selection-color: #eaffff;
    border: 1px solid #123344;
    outline: 0;
}
QLabel#status {
    color: #39ffb0;
    font-weight: 700;
    font-size: 14px;
}
QLabel#muted { color: #a5b4c0; }
QProgressBar#progress_bar {
    height: 28px;
    border: 1px solid rgba(0,234,255,80);
    border-radius: 14px;
    background: rgba(8,12,16,180);
    text-align: center;
    font-weight: 700;
    font-size: 13px;
}
QProgressBar#progress_bar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00eaff, stop:1 #7df9ff);
    border-radius: 13px;
}
QTextEdit#log_text {
    background: #0b0f14;
    color: #63ffa1;
    font-family: 'Consolas', monospace;
    font-size: 10px;
    border: 1px solid #0e1b26;
    border-radius: 8px;
}

"""
        style = style.replace('{BG_PATH}', bg_path)
        self.setStyleSheet(style)
    
    def load_images(self):
        """Load background and logo images with PyInstaller compatibility."""
        try:
            # Background handled via stylesheet now, but keep palette fallback if needed
            logo_primary = resource_path('images', 'logo-universal.png')
            logo_fallback = resource_path('images', 'logo-universal.png')
            logo_path = logo_primary if os.path.exists(logo_primary) else logo_fallback
            if os.path.exists(logo_path) and hasattr(self, 'logo_label'):
                logo_pix = QPixmap(logo_path).scaled(240, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.logo_label.setPixmap(logo_pix)
        except Exception as e:
            print(f"Image load issue: {e}")
    
    def setup_animations(self):
        """Set up fade-in animation"""
        self.setWindowOpacity(0.0)
        
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(1000)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        # Start animation after a short delay
        QTimer.singleShot(100, self.fade_animation.start)

    # Neon glow animation method removed per request
    
    def resizeEvent(self, event):
        """Handle window resize (no overlay to reposition)."""
        return super().resizeEvent(event)
    


    def log_message(self, message):
        """Add a message to the activity log"""
        self.log_text.append(message)
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def update_status(self, message):
        """Update the status label"""
        self.status_label.setText(message)
    
    def update_progress(self, value):
        """Update the progress bar"""
        if value > 0:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(int(value))
            print(f"Progress updated: {value}%")  # Debug print
        else:
            self.progress_bar.setVisible(False)
            print("Progress hidden")  # Debug print

    # (Players online feature removed at user request)
    
    def on_minimap_index_changed(self, index):
        """Enable download only when valid selection made."""
        if index > 0:
            self.download_minimap_btn.setEnabled(True)
            self.log_message(f"🗺️ Selected minimap: {self.minimap_combo.currentText()}")
        else:
            self.download_minimap_btn.setEnabled(False)
    
    def download_selected_minimap(self):
        """Download the selected minimap"""
        selected = self.minimap_combo.currentText()

        # Central mapping so any label change only needs updating here
        minimap_mapping = {
            "With Markers": "with-markers",
            "Without Markers": "without-markers",
            "With Grid & POI": "with-grid-overlay-and-poi-markers",
        }

        if selected not in minimap_mapping:
            QMessageBox.warning(self, "Selection Required", "Please select a minimap type first!")
            return

        minimap_type = minimap_mapping[selected]

        # Disable button during download
        self.download_minimap_btn.setEnabled(False)

        # Start download thread
        self.minimap_thread = DownloadThread(self.launcher_core, "minimap", minimap_type)
        self.minimap_thread.progress_updated.connect(self.update_progress)
        self.minimap_thread.status_updated.connect(self.update_status)
        self.minimap_thread.download_completed.connect(self.on_minimap_download_complete)
        self.minimap_thread.start()
    
    def on_minimap_download_complete(self, success):
        """Handle minimap download completion"""
        if success:
            self.update_status("✅ Minimap installed!")
            self.log_message("✅ Minimap installed successfully!")
            QMessageBox.information(self, "Success", 
                                  "Minimap has been installed successfully!")
            
            # Reset dropdown
            self.minimap_combo.setCurrentIndex(0)
        else:
            self.update_status("❌ Minimap download failed")
            self.log_message("❌ Minimap download failed")
            QMessageBox.critical(self, "Download Error", 
                               "Failed to download minimap!")
        
        self.update_progress(0)
    
    def check_for_updates(self, silent=False):
        """Check for updates automatically on startup"""
        def check_updates():
            try:
                if not silent:
                    self.update_status("🔍 Checking for updates...")
                    self.log_message("🔍 Checking for Tibia game updates...")

                current_version = self.launcher_core.get_current_version() or 'Not installed'
                if not silent:
                    self.log_message(f"📋 Current version: {current_version}")

                # Optional auto-install behavior from remote config
                auto_install = False
                try:
                    cfg = self.launcher_core.get_remote_config()
                    val = (cfg or {}).get('auto_install_updates')
                    if isinstance(val, bool):
                        auto_install = val
                    elif isinstance(val, str):
                        auto_install = val.strip().lower() in ("1", "true", "yes", "on")
                except Exception:
                    auto_install = False

                latest_info = self.launcher_core.get_latest_release_info()
                if latest_info:
                    latest_version = latest_info.get('version') or latest_info.get('tag_name') or latest_info.get('name') or ''
                    # Normalize leading v
                    if latest_version.lower().startswith('v') and latest_version[1:2].isdigit():
                        latest_version = latest_version[1:]

                    if not silent:
                        self.log_message(f"🌐 Latest version: {latest_version or 'Unknown'}")

                    # Decide if update is needed
                    needs_update = False
                    if latest_version:
                        if current_version == "Not installed":
                            needs_update = True
                        else:
                            try:
                                needs_update = self.launcher_core._compare_versions(current_version, latest_version) < 0
                            except Exception:
                                needs_update = (current_version != latest_version)

                    if latest_version and needs_update:
                        # Update available - make it prominent
                        self.update_status("🔄 Update available!")
                        self.log_message("🎉 New Tibia update available for download!")

                        # Automatically start download if not installed
                        if current_version == "Not installed":
                            self.log_message("📦 Tibia is not installed. Starting automatic download...")
                            self.download_and_install()
                        # If installed and auto_install is enabled, start automatically
                        elif auto_install:
                            self.log_message("⚙️ Auto-install enabled via config. Starting update...")
                            self.download_and_install()
                        # Otherwise, prompt user as before
                        elif not silent:
                            self.update_available_signal.emit(current_version, latest_version)

                    elif latest_version:
                        self.update_status("✅ Up to date")
                        if not silent:
                            self.log_message("✅ You have the latest Tibia version!")
                    else:
                        self.update_status("⚠️ Version check incomplete")
                        if not silent:
                            self.log_message("⚠️ Could not determine latest version, but release info was fetched.")
                else:
                    self.update_status("❌ Update check failed")
                    if not silent:
                        self.log_message("❌ Failed to check for updates (no release info)")
            except Exception as e:
                self.update_status("⚠️ Update check error")
                if not silent:
                    self.log_message(f"⚠️ Error checking updates: {str(e)}")
        # Run in thread to avoid blocking UI
        thread = threading.Thread(target=check_updates, daemon=True)
        thread.start()
    
    def setup_periodic_update_check(self):
        """Set up automatic periodic update checking"""
        # Create timer for periodic checks (every 2 hours = 7200000 ms)
        self.update_check_timer = QTimer()
        self.update_check_timer.timeout.connect(lambda: self.check_for_updates(silent=True))
        self.update_check_timer.start(7200000)  # 2 hours
        
        self.log_message("⏰ Automatic update checking enabled (every 2 hours)")
    
    def show_update_prompt(self, current_version, latest_version):
        """Show update prompt on main thread (connected to signal)"""
        try:
            reply = QMessageBox.question(
                self,
                "🔄 Update Available",
                f"A new Tibia version is available!\n\n"
                f"Current: {current_version}\n"
                f"Latest: {latest_version}\n\n"
                f"Would you like to download and install it now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                # Auto-start download
                self.download_and_install()
        except Exception as e:
            self.log_message(f"⚠️ Error showing update notification: {e}")
    
    # ---------------- Launcher self-update ----------------
    def _parse_version(self, v: str):
        try:
            return tuple(int(x) for x in (v.strip().lstrip('v').split('.')))
        except Exception:
            return (0,)

    def check_launcher_update(self):
        """Check remote config for a newer launcher EXE and install or prompt accordingly."""
        try:
            # Only applicable for packaged builds
            if not getattr(sys, 'frozen', False):
                self.log_message("ℹ️ Skipping launcher self-update in dev mode (not a packaged EXE).")
                return

            # Ask core to determine availability and download URL
            status = self.launcher_core.check_launcher_update()
            if not status or not isinstance(status, dict):
                return
            if not status.get('available'):
                return

            latest = status.get('latest_version', '')
            download_url = status.get('download_url')
            if not download_url:
                return

            # Read auto-install flag from remote config
            cfg = self.launcher_core.get_remote_config() or {}
            auto_install = False
            try:
                val = cfg.get('auto_install_launcher_updates') or cfg.get('auto_update_launcher')
                if isinstance(val, bool):
                    auto_install = val
                elif isinstance(val, str):
                    auto_install = val.strip().lower() in ("1", "true", "yes", "on")
            except Exception:
                auto_install = False

            if auto_install:
                self.log_message(f"⚙️ Auto-installing new launcher {latest}...")
                self.download_and_apply_launcher_update(download_url)
                return

            # Otherwise prompt the user
            reply = QMessageBox.question(
                self,
                "Update Launcher",
                f"A new launcher version {latest} is available. Update now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self.download_and_apply_launcher_update(download_url)
        except Exception as e:
            self.log_message(f"⚠️ Launcher update check error: {e}")

    # Launcher updates now use main window progress bar directly (no separate dialog)

    # Game updates now use main window progress bar directly (no separate dialog)

    def download_and_apply_launcher_update(self, url: str):
        """Download the new EXE and replace the running EXE using a temporary batch."""
        try:
            if not getattr(sys, 'frozen', False):
                self.log_message("ℹ️ Launcher self-update is only available in packaged EXE.")
                return

            # Prepare UI
            self.update_status("🔄 Preparing launcher update...")
            self.update_progress(0)
            self.log_message("🔄 Starting launcher self-update...")
            self.play_btn.setEnabled(False)

            # Progress mapper for UI
            def progress_cb(percent: float):
                try:
                    # Clamp and update main progress bar
                    pct = max(0, min(int(percent), 100))
                    self.update_progress(pct)
                    self.update_status(f"⬇️ Downloading launcher update... {pct}%")
                except Exception:
                    pass

            # Download new launcher
            temp_path = self.launcher_core.download_launcher_update(url, progress_callback=progress_cb)
            if not temp_path or not os.path.exists(temp_path):
                raise Exception("Failed to download launcher update")

            # Apply update (spawns a batch to copy and restart)
            applied = self.launcher_core.apply_launcher_update(temp_path)
            if not applied:
                raise Exception("Failed to apply launcher update")

            # Inform user and exit so the batch can replace the file
            self.update_status("🔁 Applying launcher update and restarting...")
            self.log_message("🔁 Applying launcher update and restarting...")

            # Give the UI a brief moment then quit
            QTimer.singleShot(600, QApplication.instance().quit)

        except Exception as e:
            self.log_message(f"❌ Launcher self-update failed: {e}")
            self._restore_launcher_ui()
    
    def _simulate_launcher_progress(self):
        """Deprecated: kept for reference but no longer used (real download now)."""
        try:
            self.update_status("ℹ️ Simulation disabled; performing real update when packaged.")
        except Exception:
            pass
    
    def _restore_launcher_ui(self):
        """Restore UI after launcher update completion or failure"""
        try:
            # Re-enable play button
            self.play_btn.setEnabled(True)
        except Exception:
            pass
    
    def download_and_install(self):
        """Download and install updates (called automatically by update system)"""
        
        # Update status and reset progress
        self.update_status("🔄 Preparing download...")
        self.update_progress(0)
        
        # Start download thread - use main window progress, no separate dialog
        self.download_thread = DownloadThread(self.launcher_core, "update")
        self.download_thread.progress_updated.connect(self.update_progress)
        self.download_thread.status_updated.connect(self.update_status)
        self.download_thread.download_completed.connect(self.on_download_complete)
        self.download_thread.start()
    
    def on_download_complete(self, success):
        """Handle download completion"""
        if success:
            self.update_status("✅ Installation completed!")
            self.log_message("🎉 Installation completed successfully!")
        else:
            self.update_status("❌ Installation failed")
            self.log_message("❌ Installation failed")
        
        # Reset progress
        self.update_progress(0)
    
    def launch_tibia(self):
        """Launch the Tibia client"""
        try:
            self.update_status("🚀 Launching Tibia...")
            self.launcher_core.launch_tibia()
            self.update_status("✅ Tibia launched successfully!")
            self.log_message("🚀 Tibia client launched!")
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", 
                               f"Failed to launch Tibia: {str(e)}")
            self.update_status(f"❌ Launch failed: {str(e)}")
            self.log_message(f"❌ Failed to launch: {str(e)}")
    
    def open_config_dialog(self):
        """Open configuration dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("⚙️ Launcher Configuration")
        dialog.setModal(True)
        dialog.resize(500, 300)
        
        layout = QVBoxLayout(dialog)
        
        # Installation Directory
        dir_group = QGroupBox("Installation Directory")
        dir_layout = QVBoxLayout(dir_group)
        
        current_dir_label = QLabel(f"Current: {self.launcher_core.tibia_dir}")
        current_dir_label.setWordWrap(True)
        dir_layout.addWidget(current_dir_label)
        # Quick access to installation folder
        open_btn = QPushButton("📂 Open Installation Folder")
        def open_folder():
            path = self.launcher_core.tibia_dir
            try:
                os.makedirs(path, exist_ok=True)
                from PySide6.QtGui import QDesktopServices
                from PySide6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open folder: {e}")
        open_btn.clicked.connect(open_folder)
        dir_layout.addWidget(open_btn)

        fixed_info = QLabel("Installation location is fixed to %APPDATA%/Tibia.")
        fixed_info.setWordWrap(True)
        dir_layout.addWidget(fixed_info)
        
        layout.addWidget(dir_group)
        
        # Protected Folders
        protected_group = QGroupBox("Protected Folders")
        protected_layout = QVBoxLayout(protected_group)
        
        protected_info = QLabel(
            "These folders are preserved during updates:\n"
            "• minimap\n• conf\n• characterdata"
        )
        protected_layout.addWidget(protected_info)
        
        layout.addWidget(protected_group)
        
        # --- Tibia Update section ---
        update_group = QGroupBox("Tibia Update")
        update_layout = QVBoxLayout(update_group)
        update_info = QLabel("Check for the latest Tibia client and install updates.")
        update_info.setWordWrap(True)
        update_layout.addWidget(update_info)

        check_update_btn = QPushButton("🔄 Check for Tibia Update")
        def do_manual_update():
            try:
                status = self.launcher_core.check_tibia_version_status()
                cur = status.get('current_version', 'Unknown')
                latest = status.get('latest_version', 'Unknown')
                if status.get('update_available'):
                    reply = QMessageBox.question(
                        dialog,
                        "Update Available",
                        f"A new update is available.\n\nCurrent: {cur}\nLatest: {latest}\n\nDownload and install now?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    if reply == QMessageBox.Yes:
                        dialog.accept()
                        self.download_and_install()
                else:
                    QMessageBox.information(dialog, "Up to date", f"No updates available.\nCurrent: {cur}\nLatest: {latest}")
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to check updates: {e}")
        check_update_btn.clicked.connect(do_manual_update)
        update_layout.addWidget(check_update_btn)

        # Safety: Force Download + Install (helps if detection breaks)
        force_btn = QPushButton("🛠 Safety: Download + Install")
        def do_force_install():
            reply = QMessageBox.question(
                dialog,
                "Force Install",
                "This will download the latest client and reinstall it.\n\n"
                "Your protected folders (minimap, conf, characterdata) will be preserved.\n\n"
                "Proceed?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                dialog.accept()
                # Kick off download/install regardless of current status
                try:
                    self.log_message("🛠 Starting safety download + install...")
                except Exception:
                    pass
                self.download_and_install()
        force_btn.clicked.connect(do_force_install)
        update_layout.addWidget(force_btn)
        layout.addWidget(update_group)

        # --- Launcher Update section ---
        launcher_group = QGroupBox("Launcher Update")
        launcher_layout = QVBoxLayout(launcher_group)
        launcher_info = QLabel("Manually check for a new launcher version and install it.\n"
                               "Note: Available only when running the packaged EXE.")
        launcher_info.setWordWrap(True)
        launcher_layout.addWidget(launcher_info)

        check_launcher_btn = QPushButton("🧰 Check for Launcher Update")
        def do_manual_launcher_update():
            try:
                if not getattr(sys, 'frozen', False):
                    QMessageBox.information(dialog, "Not Packaged",
                                            "Launcher self-update is only available in the packaged EXE.")
                    return
                status = self.launcher_core.check_launcher_update()
                if not status or not isinstance(status, dict):
                    QMessageBox.warning(dialog, "Update Check",
                                        "Could not determine launcher update status.")
                    return
                if not status.get('available'):
                    QMessageBox.information(dialog, "Up to date",
                                            "No new launcher version available.")
                    return
                latest = status.get('latest_version', 'unknown')
                url = status.get('download_url')
                if not url:
                    QMessageBox.warning(dialog, "Update Check",
                                        "No download URL provided by release.")
                    return
                # Prompt to proceed
                reply = QMessageBox.question(
                    dialog,
                    "Update Launcher",
                    f"A new launcher version {latest} is available.\nInstall now?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    dialog.accept()
                    self.download_and_apply_launcher_update(url)
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to check/apply launcher update: {e}")
        check_launcher_btn.clicked.connect(do_manual_launcher_update)
        launcher_layout.addWidget(check_launcher_btn)
        layout.addWidget(launcher_group)
        
        # Close button
        close_btn = QPushButton("✅ Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        # Apply dark styling to dialog
        dialog.setStyleSheet(self.styleSheet())
        
        dialog.exec()

    # Removed first-run prompt and manual browse: location is fixed to %APPDATA%


def main():
    """Main function to run the PySide6 launcher"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Use Fusion style for better dark theme support
    
    # Set application icon if available
    icon_path = resource_path('images', 'logo-universal.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    launcher = PySide6GamingLauncher()
    launcher.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()