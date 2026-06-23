from __future__ import annotations

import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

from PyQt6.QtCore import (
    QEasingCurve, QMimeData, QObject, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QDragEnterEvent, QDropEvent, QFont, QFontDatabase,
    QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget, QProgressBar,
)

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

_DEFAULT_W, _DEFAULT_H = 1050, 750
_MIN_W,     _MIN_H     = 820, 580
_LEFT_W  = 160
_RIGHT_W = 350

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"

# --- GALAXY ANDROMEDA COLOR PALETTE ---
class C:
    BG        = "#010206"  # Deepest Space Void
    PANEL     = "#080c18"  # Translucent Dark Blue/Black
    PANEL2    = "#0a1128"  # Slightly Lighter Void
    BORDER    = "#1e293b"  # Slate 800
    BORDER_B  = "#3b82f6"  # Blue 500 (Active/Highlight)
    BORDER_A  = "#334155"  # Slate 700
    PRI       = "#00d4ff"  # Bright Cyan (Primary Stars)
    PRI_DIM   = "#1d4ed8"  # Deep Blue (Galaxy Core)
    PRI_GHO   = "#172554"  # Blue 950
    ACC       = "#a855f7"  # Galactic Purple (Neural Net Thinking)
    ACC2      = "#f472b6"  # Nebula Pink (RPA Execution)
    GREEN     = "#2ecc71"  # Zero-Trust Success
    GREEN_D   = "#065f46"  # Emerald 800
    RED       = "#ef4444"  # Red 500 (Legacy/Error)
    MUTED_C   = "#f43f5e"  # Rose 500 (Muted)
    TEXT      = "#f8fafc"  # Slate 50
    TEXT_DIM  = "#94a3b8"  # Slate 400
    TEXT_MED  = "#cbd5e1"  # Slate 300
    WHITE     = "#ffffff"
    DARK      = "#02040a"  # Slate 950 variant
    BAR_BG    = "#0f172a"  # Slate 900


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c

class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.net  = 0.0   
        self.gpu  = -1.0  
        self.tmp  = -1.0  
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now
        gpu = self._get_gpu()
        tmp = self._get_temp()

        with self._lock:
            self.cpu = cpu; self.mem = mem; self.net = net; self.gpu = gpu; self.tmp = tmp

    def _get_gpu(self) -> float:
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if r.returncode == 0:
                vals = [float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
                if vals: return sum(vals) / len(vals)
        except Exception: pass
        return -1.0

    def _get_temp(self) -> float:
        try:
            temps = psutil.sensors_temperatures()
            candidates = ["coretemp", "k10temp", "cpu_thermal", "acpitz", "cpu-thermal", "zenpower", "it8688"]
            for name in candidates:
                if name in temps:
                    entries = temps[name]
                    if entries: return entries[0].current
        except Exception: pass
        return -1.0

    def snapshot(self) -> dict:
        with self._lock: return {"cpu": self.cpu, "mem": self.mem, "net": self.net, "gpu": self.gpu, "tmp": self.tmp}


_metrics = _SysMetrics()

# --- GALAXY ENGINE CANVAS ---
class HudCanvas(QWidget):
    def __init__(self, face_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._halo       = 55.0
        self._tgt_halo   = 55.0
        self._last_t     = time.time()
        self._scan       = 0.0
        self._scan2      = 180.0
        
        # Twinkling Background Stars [x_rel, y_rel, size, phase, speed]
        self._stars = [
            [random.uniform(0, 1), random.uniform(0, 1), random.uniform(0.5, 2.0), random.uniform(0, math.pi*2), random.uniform(0.01, 0.04)]
            for _ in range(150)
        ]
        
        # Andromeda Spiral Particles (Clean orbital dots) [radius_frac, angle, speed, size, color_idx]
        self._galaxy_particles = []
        for _ in range(400):
            arm = random.randint(0, 3) 
            base_angle = arm * (math.pi / 2)
            r = random.uniform(0.02, 1.0)
            angle_offset = random.gauss(0, 0.4)
            speed = 0.015 / (r + 0.15) 
            size = random.uniform(1.0, 2.5)
            color_idx = random.choice([0, 0, 1, 1, 2]) # White, Cyan, Blue
            self._galaxy_particles.append([r, base_angle + angle_offset, speed, size, color_idx])

        # Neural Constellation Nodes (Special interaction nodes) [radius_frac, angle, speed, size]
        self._nodes = []
        for _ in range(28):
            arm = random.randint(0, 3)
            base_angle = arm * (math.pi / 2)
            r = random.uniform(0.15, 0.9)
            angle_offset = random.gauss(0, 0.3)
            speed = 0.015 / (r + 0.15)
            size = random.uniform(2.5, 4.0)
            self._nodes.append([r, base_angle + angle_offset, speed, size])

        self._blink      = True
        self._blink_tick = 0
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def _step(self):
        self._tick += 1
        now = time.time()
        if now - self._last_t > (0.12 if self.speaking else 0.5):
            if self.speaking:
                self._tgt_scale = random.uniform(1.06, 1.14)
                self._tgt_halo  = random.uniform(145, 190)
            elif self.muted:
                self._tgt_scale = random.uniform(0.998, 1.002)
                self._tgt_halo  = random.uniform(15, 28)
            else:
                self._tgt_scale = random.uniform(1.001, 1.008)
                self._tgt_halo  = random.uniform(48, 68)
            self._last_t = now

        sp = 0.38 if self.speaking else 0.15
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo  += (self._tgt_halo  - self._halo)  * sp
        
        self._scan  = (self._scan  + (3.0 if self.speaking else 1.3)) % 360
        self._scan2 = (self._scan2 + (-2.0 if self.speaking else -0.75)) % 360

        for s in self._stars:
            s[3] += s[4]

        # Gentle speed up during processing, but keep it elegant, not chaotic
        is_processing = self.state in ["THINKING", "PROCESSING"]
        speed_mult = 3.5 if self.speaking else (2.0 if is_processing else 0.6)
        
        for p in self._galaxy_particles:
            p[1] += p[2] * speed_mult
            
        for n in self._nodes:
            n[1] += n[2] * speed_mult

        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), qcol(C.BG))

        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H)

        # 1. Background Starfield
        for s in self._stars:
            x, y = s[0] * W, s[1] * H
            alpha = max(20, min(200, int(127 + 128 * math.sin(s[3]))))
            p.setPen(QPen(qcol(C.WHITE, alpha), s[2]))
            p.drawPoint(QPointF(x, y))

        # 2. Galactic Core Glow
        core_r = fw * 0.35 * self._scale
        tilt = 0.45 # 3D disk inclination (1.0 = flat, 0.1 = edge on)

        grad = QRadialGradient(cx, cy, core_r)
        glow_alpha = max(0, min(255, int(self._halo * 1.8)))
        
        if self.muted:
            base_col, core_col = C.MUTED_C, C.RED
        else:
            base_col, core_col = C.WHITE, C.PRI_DIM

        grad.setColorAt(0.0, qcol(base_col, glow_alpha))
        grad.setColorAt(0.15, qcol(C.PRI, int(glow_alpha * 0.7)))
        grad.setColorAt(0.5, qcol(core_col, int(glow_alpha * 0.3)))
        grad.setColorAt(1.0, qcol(C.BG, 0))
        
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), core_r, core_r * tilt)

        # 3. Andromeda Spiral Dust (Clean Orbiting Dots)
        colors = [C.WHITE, C.PRI, C.PRI_DIM]
        for pt in self._galaxy_particles:
            r = pt[0] * fw * 0.45 * self._scale
            winding = 4.0 
            current_angle = pt[1] - (pt[0] * winding) 
            
            x = cx + r * math.cos(current_angle)
            y = cy + r * math.sin(current_angle) * tilt
            
            c_idx = pt[4]
            alpha = max(20, min(255, int((1.1 - pt[0]) * 200 * (self._halo/60.0))))
            if self.muted: c_idx = 0; alpha = int(alpha * 0.5)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(colors[c_idx], alpha)))
            p.drawEllipse(QPointF(x, y), pt[3], pt[3])

        # 4. Neural Constellation Network (The Interaction Lines)
        is_processing = self.state in ["THINKING", "PROCESSING"]
        
        # Calculate current positions of nodes
        node_coords = []
        for n in self._nodes:
            r = n[0] * fw * 0.45 * self._scale
            winding = 4.0
            current_angle = n[1] - (n[0] * winding)
            x = cx + r * math.cos(current_angle)
            y = cy + r * math.sin(current_angle) * tilt
            node_coords.append((x, y, n))

        if is_processing and not self.muted:
            # Change color based on state (Thinking = Purple, Processing = Pink)
            net_col = C.ACC if self.state == "THINKING" else C.ACC2
            conn_dist = fw * 0.18 # Maximum connection distance
            
            # Draw Constellation Lines
            for i in range(len(node_coords)):
                x1, y1, n1 = node_coords[i]
                for j in range(i + 1, len(node_coords)):
                    x2, y2, n2 = node_coords[j]
                    dist = math.hypot(x2 - x1, y2 - y1)
                    
                    if dist < conn_dist:
                        # Fade line based on distance
                        alpha = max(0, int(255 * (1.0 - (dist / conn_dist))))
                        alpha = int(alpha * min(1.0, self._halo / 80.0)) # Smooth fade with halo
                        
                        if alpha > 0:
                            p.setPen(QPen(qcol(net_col, alpha), 1.2))
                            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            
            # Draw Constellation Nodes (Bright cores)
            for x, y, n in node_coords:
                # Center white dot
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(qcol(C.WHITE, 220)))
                p.drawEllipse(QPointF(x, y), n[3], n[3])
                
                # Outer glowing ring
                p.setPen(QPen(qcol(net_col, 180), 1.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(x, y), n[3] + 2.5, n[3] + 2.5)

        # 5. Deep-Space HUD Tech Overlays
        track_r = fw * 0.48
        p.setPen(QPen(qcol(C.PRI_GHO, 150), 1, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), track_r, track_r * tilt)

        sr = fw * 0.49
        sa = min(255, int(self._halo * 1.5))
        ex = 85 if self.speaking else 50
        
        p.setPen(QPen(qcol(C.ACC if self.state == "THINKING" else C.PRI, sa), 2.0))
        srect = QRectF(cx - sr, cy - sr * tilt, sr * 2, sr * 2 * tilt)
        p.drawArc(srect, int(self._scan * 16), int(ex * 16))
        
        p.setPen(QPen(qcol(C.WHITE, sa // 2), 1.0))
        p.drawArc(srect, int(self._scan2 * 16), int(ex * 16))

        # 6. Status Text
        sy = cy + fw * 0.35
        if self.muted:
            txt, col = "⊘ SENSOR MUTED", qcol(C.MUTED_C)
        elif self.speaking:
            txt, col = "● SPEAKING", qcol(C.WHITE)
        elif self.state == "THINKING":
            sym = "◈" if self._blink else "◇"
            txt, col = f"{sym} ORCHESTRATING", qcol(C.ACC)
        elif self.state == "PROCESSING":
            sym = "▷" if self._blink else "▶"
            txt, col = f"{sym} EXECUTING RPA", qcol(C.ACC2)
        elif self.state == "LISTENING":
            sym = "●" if self._blink else "○"
            txt, col = f"{sym} AUTOPILOT READY", qcol(C.PRI)
        else:
            sym = "●" if self._blink else "○"
            txt, col = f"{sym} {self.state}", qcol(C.PRI)

        p.setPen(QPen(col, 1))
        p.setFont(QFont("JetBrains Mono", 10, QFont.Weight.Bold))
        p.fillRect(QRectF(cx - 80, sy - 15, 160, 22), qcol(C.BG, 180))
        p.drawText(QRectF(0, sy - 18, W, 26), Qt.AlignmentFlag.AlignCenter, txt)


class MetricBar(QWidget):
    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0       
        self._text  = "--"
        self.setFixedHeight(38)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        self._value = max(0.0, min(100.0, pct))
        self._text  = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 4, 4)

        bar_h   = 4
        bar_y   = H - bar_h - 5
        bar_w   = W - 12
        bar_x   = 6
        fill_w  = int(bar_w * self._value / 100)

        p.setBrush(QBrush(qcol(C.BAR_BG)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

        if self._value > 85: bar_col = qcol(C.RED)
        elif self._value > 65: bar_col = qcol(C.ACC2)
        else: bar_col = qcol(self._color)

        if fill_w > 0:
            p.setBrush(QBrush(bar_col))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2, 2)

        p.setFont(QFont("JetBrains Mono", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(8, 5, 50, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        p.setFont(QFont("JetBrains Mono", 9, QFont.Weight.Bold))
        p.setPen(QPen(bar_col if self._text != "--" else qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 4, W - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)

class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("JetBrains Mono", 9))
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {C.PANEL};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 6px;
                padding: 10px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_A};
                border-radius: 3px;
                min-height: 20px;
            }}
        """)
        self._queue: list[str] = []
        self._typing  = False
        self._text    = ""
        self._pos     = 0
        self._tag     = "sys"
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        self._queue.append(text)
        if not self._typing:
            self._next()

    def _next(self):
        if not self._queue:
            self._typing = False
            return
        self._typing = True
        self._text   = self._queue.pop(0)
        self._pos    = 0
        tl = self._text.lower()
        if   tl.startswith("you:"):    self._tag = "you"
        elif tl.startswith("jarvis:"): self._tag = "ai"
        elif tl.startswith("andromeda:"): self._tag = "ai"
        elif tl.startswith("file:"):   self._tag = "file"
        elif "err" in tl:              self._tag = "err"
        else:                          self._tag = "sys"
        self._tmr.start(6)

    def _step(self):
        if self._pos < len(self._text):
            ch  = self._text[self._pos]
            cur = self.textCursor()
            fmt = cur.charFormat()
            col = {
                "you":  qcol(C.WHITE),
                "ai":   qcol(C.PRI),
                "err":  qcol(C.RED),
                "file": qcol(C.GREEN),
                "sys":  qcol(C.TEXT_DIM),
            }.get(self._tag, qcol(C.TEXT))
            fmt.setForeground(QBrush(col))
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText(ch, fmt)
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            self._pos += 1
        else:
            self._tmr.stop()
            cur = self.textCursor()
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n")
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            QTimer.singleShot(20, self._next)

_FILE_ICONS = {
    "image":   ("🖼", "#00d4ff"), "video":   ("🎬", "#a855f7"),
    "audio":   ("🎵", "#f472b6"), "pdf":     ("📄", "#ef4444"),
    "word":    ("📝", "#3b82f6"), "excel":   ("📊", "#22c55e"),
    "code":    ("💻", "#f59e0b"), "archive": ("📦", "#f97316"),
    "pptx":    ("📊", "#ea580c"), "text":    ("📃", "#94a3b8"),
    "data":    ("🔧", "#0ea5e9"), "unknown": ("📎", "#64748b"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                     "pdf"),
    **dict.fromkeys(["doc","docx"],                                              "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                        "excel"),
    **dict.fromkeys(["ppt","pptx"],                                              "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],   "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                   "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                    "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                  "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(110)
        self._current_file: str | None = None
        self._hovering  = False
        self._drag_over = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e: QDropEvent):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True; self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False; self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for ANDROMEDA Zero-Trust Extraction", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z    = self._z
        W, H = self.width(), self.height()
        pad  = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        bg_col = qcol("#0f172a" if z._drag_over else ("#1e293b" if z._hovering else C.PANEL))
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 8, 8)

        if z._current_file:   border_col = qcol(C.GREEN, 200)
        elif z._drag_over:    border_col = qcol(C.PRI, 230)
        elif z._hovering:     border_col = qcol(C.BORDER_B, 200)
        else:                 border_col = qcol(C.BORDER, 160)

        pen = QPen(border_col, 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 8, 8)

        if z._current_file:   self._paint_file(p, W, H)
        elif z._drag_over:    self._paint_drag_over(p, W, H)
        else:                 self._paint_idle(p, W, H, z._hovering)

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col, 2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 4))
        p.drawLine(QPointF(cx - 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 14, cy + 4), QPointF(cx + 14, cy + 4))
        p.setFont(QFont("JetBrains Mono", 9))
        p.setPen(QPen(qcol(C.TEXT_DIM if not hover else C.TEXT), 1))
        p.drawText(QRectF(0, cy + 8, W, 16), Qt.AlignmentFlag.AlignCenter,
                   "Load Local Documents")
        p.setFont(QFont("JetBrains Mono", 7))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawText(QRectF(0, cy + 24, W, 14), Qt.AlignmentFlag.AlignCenter,
                   "Zero-Trust Sandbox Active")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(QFont("JetBrains Mono", 20))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "⬇")
        p.setFont(QFont("JetBrains Mono", 9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, "Release to Securitize")

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat  = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str  = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 12, 60
        p.setFont(QFont("Segoe UI Emoji", 24) if _OS == "Windows" else QFont("Arial", 24))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(QFont("JetBrains Mono", 9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(QFont("JetBrains Mono", 8))
        p.setPen(QPen(qcol(C.GREEN), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"Secured  ·  {ext_str}  ·  {size_str}")

        p.setFont(QFont("JetBrains Mono", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        par = str(path.parent)
        if len(par) > 42: par = "…" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 36, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(QFont("JetBrains Mono", 11, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 200), 1))
        p.drawText(QRectF(W - 38, 0, 32, H), Qt.AlignmentFlag.AlignCenter, "✕")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 38:
            z.clear_file()
        else:
            z.mousePressEvent(e)


class SetupOverlay(QWidget):
    done = pyqtSignal(str)

    def __init__(self, parent=None, initial: dict | None = None, mode: str = "init"):
        super().__init__(parent)
        self._mode = mode
        _init = initial or {}
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: rgba(2, 6, 23, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 12px;
                backdrop-filter: blur(15px);
            }}
        """)

        _INPUT = f"""
            QLineEdit {{
                background: {C.DARK}; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 6px; padding: 6px 10px;
                font-family: 'JetBrains Mono', monospace; font-size: 9pt;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """

        self._sel_stt          = _init.get("stt_engine",    "whisper")
        self._sel_tts          = _init.get("tts_engine",    "edgetts")
        self._sel_llm_provider = _init.get("llm_provider",  "ollama")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        def _lbl(txt, sz=9, bold=False, col=C.PRI, align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt); w.setAlignment(align)
            w.setFont(QFont("Plus Jakarta Sans", sz,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {col}; background: transparent;")
            return w

        def _sep():
            s = QFrame(); s.setFrameShape(QFrame.Shape.HLine)
            s.setStyleSheet(f"color: {C.BORDER}; margin: 6px 0;")
            return s

        def _input(placeholder="", pw=False, fixed_h=32):
            w = QLineEdit()
            w.setPlaceholderText(placeholder)
            w.setFixedHeight(fixed_h)
            if pw:
                w.setEchoMode(QLineEdit.EchoMode.Password)
            w.setStyleSheet(_INPUT)
            return w

        def _toggle_row(keys_labels: list, getter, setter):
            row = QHBoxLayout(); row.setSpacing(8)
            btns: dict[str, QPushButton] = {}
            def _click(k):
                setter(k)
                for bk, b in btns.items():
                    _style_btn(b, bk == k)
            for k, lbl in keys_labels:
                b = QPushButton(lbl)
                b.setFixedHeight(30)
                b.setFont(QFont("Plus Jakarta Sans", 9, QFont.Weight.Bold))
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.clicked.connect(lambda _, kk=k: _click(kk))
                row.addWidget(b)
                btns[k] = b
            _click(getter())
            return row, btns

        def _style_btn(btn: QPushButton, active: bool):
            if active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PRI}; color: {C.BG};
                        border: none; border-radius: 6px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.DARK}; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 6px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
                """)

        if mode == "config":
            layout.addWidget(_lbl("ANDROMEDA CONFIGURATION", 13, True))
            layout.addWidget(_lbl("Modify Telemetry and Autopilot Settings.", 9, col=C.TEXT_DIM))
        else:
            layout.addWidget(_lbl("ANDROMEDA INITIALIZATION", 13, True))
            layout.addWidget(_lbl("Configure Orchestration Engine before launch.", 9, col=C.TEXT_DIM))
        layout.addWidget(_sep())

        layout.addWidget(_lbl("SPEECH-TO-TEXT ENGINE", 8, bold=True, col=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        stt_row, self._stt_btns = _toggle_row(
            [("whisper","🎙 Whisper"), ("vosk","🔊 Vosk")],
            lambda: self._sel_stt,
            self._set_stt,
        )
        layout.addLayout(stt_row)

        _COMBO_STYLE = f"""
            QComboBox {{
                background: {C.DARK}; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 6px; padding: 4px 8px;
                font-family: 'JetBrains Mono', monospace; font-size: 9pt;
            }}
            QComboBox:focus {{ border: 1px solid {C.PRI}; }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
            QComboBox QAbstractItemView {{
                background: {C.DARK}; color: {C.TEXT};
                border: 1px solid {C.BORDER};
                selection-background-color: {C.PRI_GHO};
                font-family: 'JetBrains Mono', monospace; font-size: 9pt;
            }}
        """

        stt_detail = QHBoxLayout(); stt_detail.setSpacing(8)
        stt_detail.addWidget(_lbl("Model:", 8, col=C.TEXT_MED,
                                   align=Qt.AlignmentFlag.AlignRight))

        self._whisper_combo = QComboBox()
        self._whisper_combo.setFixedHeight(32)
        self._whisper_combo.setStyleSheet(_COMBO_STYLE)
        for m in ["tiny", "base", "small", "medium", "large-v3"]:
            self._whisper_combo.addItem(m)
        _cur_model = _init.get("stt_model", "base")
        _idx = self._whisper_combo.findText(_cur_model)
        self._whisper_combo.setCurrentIndex(_idx if _idx >= 0 else 1)
        stt_detail.addWidget(self._whisper_combo)

        self._vosk_model_input = _input("model dir path (auto-download if empty)")
        self._vosk_model_input.setText(_init.get("vosk_model_path", ""))
        stt_detail.addWidget(self._vosk_model_input)

        layout.addLayout(stt_detail)

        self._whisper_combo.setVisible(self._sel_stt == "whisper")
        self._vosk_model_input.setVisible(self._sel_stt == "vosk")

        stt_lang_row = QHBoxLayout(); stt_lang_row.setSpacing(8)
        stt_lang_row.addWidget(_lbl("Language:", 8, col=C.TEXT_MED,
                                    align=Qt.AlignmentFlag.AlignRight))
        self._stt_lang_input = _input("auto (tr / en / de / fr...)")
        self._stt_lang_input.setText(_init.get("stt_language", "auto"))
        stt_lang_row.addWidget(self._stt_lang_input)
        layout.addLayout(stt_lang_row)
        layout.addWidget(_sep())

        layout.addWidget(_lbl("COGNITIVE ENGINE (LLM)", 8, bold=True, col=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))

        llm_prov_row, self._llm_prov_btns = _toggle_row(
            [
                ("ollama", "🦙 Ollama"),
                ("openai", "🔌 OpenAI / LM Studio"),
            ],
            lambda: self._sel_llm_provider,
            self._set_llm_provider,
        )
        layout.addLayout(llm_prov_row)

        _ollama_hint = "ollama.com · run: ollama pull qwen-plus"
        _openai_hint = "Requires DashScope / Local Server"
        self._llm_hint_lbl = _lbl(
            _openai_hint if self._sel_llm_provider == "openai" else _ollama_hint,
            8, col=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft
        )
        layout.addWidget(self._llm_hint_lbl)

        llm_row = QHBoxLayout(); llm_row.setSpacing(8)
        llm_row.addWidget(_lbl("URL:", 8, col=C.TEXT_MED,
                                align=Qt.AlignmentFlag.AlignRight))
        _default_url = _init.get("llm_url",
                                  "http://localhost:1234" if self._sel_llm_provider == "openai"
                                  else "http://localhost:11434")
        self._llm_url_input = _input()
        self._llm_url_input.setText(_default_url)
        llm_row.addWidget(self._llm_url_input, stretch=2)
        llm_row.addWidget(_lbl("Model:", 8, col=C.TEXT_MED,
                                align=Qt.AlignmentFlag.AlignRight))
        self._llm_model_input = _input("qwen-plus / mistral")
        self._llm_model_input.setText(_init.get("llm_model", ""))
        llm_row.addWidget(self._llm_model_input, stretch=2)
        layout.addLayout(llm_row)
        layout.addWidget(_sep())

        layout.addWidget(_lbl("VOICE SYNTHESIS ENGINE", 8, bold=True, col=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        tts_row, self._tts_btns = _toggle_row(
            [("edgetts","🔈 EdgeTTS"), ("kokoro","🤖 Kokoro"), ("elevenlabs","⚡ ElevenLabs")],
            lambda: self._sel_tts,
            self._set_tts,
        )
        layout.addLayout(tts_row)

        voice_row = QHBoxLayout(); voice_row.setSpacing(8)
        self._voice_lbl = QLabel("Voice:")
        self._voice_lbl.setFont(QFont("Plus Jakarta Sans", 8))
        self._voice_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._voice_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        voice_row.addWidget(self._voice_lbl)

        self._tts_voice_input = _input("en-US-GuyNeural")
        self._tts_voice_input.setText(_init.get("tts_voice", "en-US-GuyNeural"))
        voice_row.addWidget(self._tts_voice_input)

        self._kokoro_combo = QComboBox()
        self._kokoro_combo.setFixedHeight(32)
        self._kokoro_combo.setStyleSheet(_COMBO_STYLE)
        _KOKORO_VOICES = [
            ("af_heart",    "af_heart  — EN-F warm"),
            ("af_sky",      "af_sky  — EN-F clear"),
            ("am_adam",     "am_adam  — EN-M adam"),
        ]
        for val, display in _KOKORO_VOICES:
            self._kokoro_combo.addItem(display, userData=val)
        _cur_voice = _init.get("tts_voice", "af_heart")
        for i in range(self._kokoro_combo.count()):
            if self._kokoro_combo.itemData(i) == _cur_voice:
                self._kokoro_combo.setCurrentIndex(i)
                break
        self._kokoro_combo.setVisible(False)
        voice_row.addWidget(self._kokoro_combo)

        layout.addLayout(voice_row)

        self._kokoro_speed_widget = QWidget()
        self._kokoro_speed_widget.setStyleSheet("background: transparent;")
        ks_row = QHBoxLayout(self._kokoro_speed_widget)
        ks_row.setContentsMargins(0, 0, 0, 0)
        ks_row.setSpacing(8)
        ks_row.addWidget(_lbl("Speed:", 8, col=C.TEXT_MED,
                               align=Qt.AlignmentFlag.AlignRight))
        self._kokoro_speed_combo = QComboBox()
        self._kokoro_speed_combo.setFixedHeight(32)
        self._kokoro_speed_combo.setStyleSheet(_COMBO_STYLE)
        for val, label in [("1.0", "1.0× Normal"), ("1.2", "1.2× Fast")]:
            self._kokoro_speed_combo.addItem(label, userData=val)
        _cur_speed = str(_init.get("tts_speed", "1.2"))
        for i in range(self._kokoro_speed_combo.count()):
            if self._kokoro_speed_combo.itemData(i) == _cur_speed:
                self._kokoro_speed_combo.setCurrentIndex(i)
                break
        ks_row.addWidget(self._kokoro_speed_combo)
        layout.addWidget(self._kokoro_speed_widget)

        self._el_key_widget = QWidget()
        self._el_key_widget.setStyleSheet("background: transparent;")
        el_row = QHBoxLayout(self._el_key_widget)
        el_row.setContentsMargins(0, 0, 0, 0)
        el_row.setSpacing(8)
        el_row.addWidget(_lbl("API Key:", 8, col=C.TEXT_MED,
                               align=Qt.AlignmentFlag.AlignRight))
        self._el_key_input = _input("ElevenLabs API key", pw=True)
        self._el_key_input.setText(_init.get("elevenlabs_api_key", ""))
        el_row.addWidget(self._el_key_input)
        layout.addWidget(self._el_key_widget)

        layout.addWidget(_sep())
        self._update_tts_ui(self._sel_tts)

        btn_row = QHBoxLayout(); btn_row.setSpacing(12)

        if mode == "config":
            cancel_btn = QPushButton("✕ CANCEL")
            cancel_btn.setFont(QFont("Plus Jakarta Sans", 10, QFont.Weight.Bold))
            cancel_btn.setFixedHeight(38)
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.DARK}; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 6px;
                }}
                QPushButton:hover {{
                    color: {C.RED}; border: 1px solid {C.RED};
                }}
            """)
            cancel_btn.clicked.connect(self.hide)
            btn_row.addWidget(cancel_btn)

        btn_label = "EXECUTE CONFIGURATION" if mode == "config" else "INITIALIZE AUTOPILOT"
        init_btn = QPushButton(btn_label)
        init_btn.setFont(QFont("Plus Jakarta Sans", 10, QFont.Weight.Bold))
        init_btn.setFixedHeight(38)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PRI}; color: {C.BG};
                border: none; border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {C.PRI_DIM}; color: {C.WHITE};
            }}
        """)
        init_btn.clicked.connect(self._submit)
        btn_row.addWidget(init_btn)
        layout.addLayout(btn_row)

    def _update_tts_ui(self, key: str) -> None:
        if not hasattr(self, "_voice_lbl"):
            return
        is_kokoro = (key == "kokoro")
        if hasattr(self, "_tts_voice_input"):
            self._tts_voice_input.setVisible(not is_kokoro)
        if hasattr(self, "_kokoro_combo"):
            self._kokoro_combo.setVisible(is_kokoro)

        if key == "elevenlabs":
            self._voice_lbl.setText("Voice ID:")
            if hasattr(self, "_tts_voice_input"):
                self._tts_voice_input.setPlaceholderText("ElevenLabs voice ID")
        elif key == "kokoro":
            self._voice_lbl.setText("Voice:")
        else:
            self._voice_lbl.setText("Voice:")
            if hasattr(self, "_tts_voice_input"):
                self._tts_voice_input.setPlaceholderText("en-US-GuyNeural")

        if hasattr(self, "_kokoro_speed_widget"):
            self._kokoro_speed_widget.setVisible(is_kokoro)
        if hasattr(self, "_el_key_widget"):
            self._el_key_widget.setVisible(key == "elevenlabs")

    def _set_llm_provider(self, key: str):
        self._sel_llm_provider = key
        if not hasattr(self, "_llm_prov_btns"):
            return
        for k, btn in self._llm_prov_btns.items():
            active = (k == key)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {'#00d4ff' if active else C.DARK};
                    color: {'#010206' if active else C.TEXT_DIM};
                    border: {'none' if active else f'1px solid {C.BORDER}'};
                    border-radius: 6px; font-weight: {'bold' if active else 'normal'};
                }}
                QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
            """)
        if hasattr(self, "_llm_url_input"):
            if key == "openai":
                self._llm_url_input.setPlaceholderText("http://localhost:1234")
                cur = self._llm_url_input.text().strip()
                if not cur or cur == "http://localhost:11434":
                    self._llm_url_input.setText("http://localhost:1234")
            else:
                self._llm_url_input.setPlaceholderText("http://localhost:11434")
                cur = self._llm_url_input.text().strip()
                if not cur or cur == "http://localhost:1234":
                    self._llm_url_input.setText("http://localhost:11434")
        if hasattr(self, "_llm_hint_lbl"):
            if key == "openai":
                self._llm_hint_lbl.setText("Requires DashScope / Local Server API")
            else:
                self._llm_hint_lbl.setText("ollama.com · run: ollama pull qwen-plus")

    def _set_stt(self, key: str):
        self._sel_stt = key
        if not hasattr(self, "_stt_btns"):
            return
        for k, btn in self._stt_btns.items():
            active = (k == key)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {'#00d4ff' if active else C.DARK};
                    color: {'#010206' if active else C.TEXT_DIM};
                    border: {'none' if active else f'1px solid {C.BORDER}'};
                    border-radius: 6px; font-weight: {'bold' if active else 'normal'};
                }}
                QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
            """)
        if hasattr(self, "_whisper_combo"):
            self._whisper_combo.setVisible(key == "whisper")
        if hasattr(self, "_vosk_model_input"):
            self._vosk_model_input.setVisible(key == "vosk")

    def _set_tts(self, key: str):
        self._sel_tts = key
        if not hasattr(self, "_tts_btns"):
            return
        for k, btn in self._tts_btns.items():
            active = (k == key)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {'#00d4ff' if active else C.DARK};
                    color: {'#010206' if active else C.TEXT_DIM};
                    border: {'none' if active else f'1px solid {C.BORDER}'};
                    border-radius: 6px; font-weight: {'bold' if active else 'normal'};
                }}
                QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
            """)
        self._update_tts_ui(key)

    def _submit(self):
        llm_model = self._llm_model_input.text().strip()
        if not llm_model:
            self._llm_model_input.setStyleSheet(
                self._llm_model_input.styleSheet() +
                f" QLineEdit {{ border: 1px solid {C.RED}; }}"
            )
            return

        if self._sel_stt == "whisper":
            stt_model = self._whisper_combo.currentText()
        else:
            stt_model = self._vosk_model_input.text().strip()

        if self._sel_tts == "kokoro":
            tts_voice = self._kokoro_combo.currentData() or "af_heart"
            tts_speed = self._kokoro_speed_combo.currentData() or "1.2"
        else:
            tts_voice = self._tts_voice_input.text().strip() or "en-US-GuyNeural"
            tts_speed = "1.0"

        _provider = getattr(self, "_sel_llm_provider", "ollama")
        _default_url = "http://localhost:1234" if _provider == "openai" else "http://localhost:11434"
        cfg = {
            "stt_engine":         self._sel_stt,
            "stt_model":          stt_model,
            "stt_language":       self._stt_lang_input.text().strip() or "auto",
            "llm_provider":       _provider,
            "llm_url":            self._llm_url_input.text().strip() or _default_url,
            "llm_model":          llm_model,
            "tts_engine":         self._sel_tts,
            "tts_voice":          tts_voice,
            "tts_speed":          tts_speed,
            "elevenlabs_api_key": self._el_key_input.text().strip(),
        }
        if self._sel_stt == "vosk" and stt_model:
            cfg["vosk_model_path"] = stt_model
        self.done.emit(json.dumps(cfg))


class StartupPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            StartupPanel {{
                background: rgba(2, 6, 23, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 12px;
                backdrop-filter: blur(15px);
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 24, 32, 24)
        lay.setSpacing(12)

        title = QLabel("SYSTEMS INITIALIZATION")
        title.setFont(QFont("Plus Jakarta Sans", 12, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lay.addWidget(title)

        lay.addSpacing(4)

        self._rows: dict[str, dict] = {}
        _COMPS = [
            ("stt", "SPEECH RECOGNITION (STT)", C.GREEN),
            ("llm", "ORCHESTRATION ENGINE (LLM)", C.ACC),
            ("tts", "VOICE SYNTHESIS (TTS)", C.PRI),
        ]
        for key, label, color in _COMPS:
            box = QWidget()
            box.setStyleSheet(
                f"background: {C.DARK}; border: 1px solid {C.BORDER}; border-radius: 6px;"
            )
            box_lay = QVBoxLayout(box)
            box_lay.setContentsMargins(12, 8, 12, 8)
            box_lay.setSpacing(6)

            top = QHBoxLayout()
            nm = QLabel(label)
            nm.setFont(QFont("JetBrains Mono", 9, QFont.Weight.Bold))
            nm.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
            top.addWidget(nm)
            top.addStretch()

            st = QLabel("LOADING...")
            st.setFont(QFont("JetBrains Mono", 9, QFont.Weight.Bold))
            st.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
            top.addWidget(st)
            box_lay.addLayout(top)

            bar = QProgressBar()
            bar.setFixedHeight(6)
            bar.setRange(0, 0)
            bar.setTextVisible(False)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background: {C.BORDER}; border: none; border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {C.BORDER}, stop:1 {color});
                    border-radius: 3px; width: 60px; margin: 0px;
                }}
            """)
            box_lay.addWidget(bar)
            lay.addWidget(box)
            self._rows[key] = {"bar": bar, "status": st, "color": color}

        lay.addSpacing(8)

        self._status_lbl = QLabel("Initializing local nodes...")
        self._status_lbl.setFont(QFont("JetBrains Mono", 9))
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._status_lbl.setWordWrap(True)
        lay.addWidget(self._status_lbl)

        tip = QLabel("100% Local Deployment. Zero-Trust Sandbox Active.")
        tip.setFont(QFont("Plus Jakarta Sans", 8))
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip.setStyleSheet(f"color: {C.BORDER_A}; background: transparent;")
        lay.addWidget(tip)

    def update_component(self, key: str, status: str) -> None:
        if key not in self._rows:
            return
        row = self._rows[key]
        ok     = status == "ready"
        color  = row["color"] if ok else C.RED
        label  = "SECURED" if ok else "ERROR ✗"

        bar = row["bar"]
        bar.setRange(0, 100)
        bar.setValue(100)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background: {C.BAR_BG}; border: none; border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: {color}; border-radius: 3px;
            }}
        """)
        st = row["status"]
        st.setText(label)
        st.setStyleSheet(f"color: {color}; background: transparent; border: none;")

    def set_status(self, text: str) -> None:
        self._status_lbl.setText(text)
        col = C.GREEN if "online" in text.lower() else C.TEXT_DIM
        self._status_lbl.setStyleSheet(f"color: {col}; background: transparent;")


class MainWindow(QMainWindow):
    _log_sig     = pyqtSignal(str)
    _state_sig   = pyqtSignal(str)
    _startup_sig = pyqtSignal(str, str) 

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowTitle("ANDROMEDA — ENTERPRISE AUTOPILOT")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command  = None
        self._muted           = False
        self._current_file: str | None = None

        central = QWidget()
        central.setStyleSheet(f"background: {C.BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._left_panel = self._build_left_panel()
        body.addWidget(self._left_panel, stretch=0)

        self.hud = HudCanvas(face_path)
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.addWidget(self.hud, stretch=5)

        self._right_panel = self._build_right_panel()
        body.addWidget(self._right_panel, stretch=0)

        root.addLayout(body, stretch=1)
        root.addWidget(self._build_footer())

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(2000)
        self._update_metrics()

        self._log_sig.connect(self._log.append_log)
        self._state_sig.connect(self._apply_state)
        self._startup_sig.connect(self._on_startup_sig)

        self._overlay: SetupOverlay | None = None
        self._startup_panel: StartupPanel | None = None
        self._on_reconfigure_cb = None
        self._ready = self._check_config()
        if not self._ready:
            self._show_setup()

        sc_mute = QShortcut(QKeySequence("F4"), self)
        sc_mute.activated.connect(self._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"), self)
        sc_full.activated.connect(self._toggle_fullscreen)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cw = self.centralWidget()
        if self._overlay and self._overlay.isVisible():
            ow, oh = 580, 680
            self._overlay.setGeometry((cw.width() - ow) // 2, (cw.height() - oh) // 2, ow, oh)
        if self._startup_panel and self._startup_panel.isVisible():
            pw, ph = 480, 380
            self._startup_panel.setGeometry((cw.width() - pw) // 2, (cw.height() - ph) // 2, pw, ph)

    def _on_startup_sig(self, action: str, data: str) -> None:
        if action == "show":
            self._create_startup_panel()
        elif action in ("ready", "error"):
            if self._startup_panel:
                self._startup_panel.update_component(data, action)
        elif action == "status":
            if self._startup_panel:
                self._startup_panel.set_status(data)
        elif action == "hide":
            if self._startup_panel:
                QTimer.singleShot(1200, self._destroy_startup_panel)

    def _create_startup_panel(self) -> None:
        if self._startup_panel and self._startup_panel.isVisible():
            return
        cw = self.centralWidget()
        pw, ph = 480, 380
        panel = StartupPanel(cw)
        panel.setGeometry((cw.width() - pw) // 2, (cw.height() - ph) // 2, pw, ph)
        panel.show()
        panel.raise_()
        self._startup_panel = panel

    def _destroy_startup_panel(self) -> None:
        if self._startup_panel:
            self._startup_panel.hide()
            self._startup_panel.deleteLater()
            self._startup_panel = None

    def _update_metrics(self):
        snap = _metrics.snapshot()
        cpu = snap["cpu"]
        self._bar_cpu.set_value(cpu, f"{cpu:.0f}%")
        mem = snap["mem"]
        self._bar_mem.set_value(mem, f"{mem:.0f}%")
        net = snap["net"]
        if net < 1.0: net_str = f"{net*1024:.0f}KB/s"
        else: net_str = f"{net:.1f}MB/s"
        net_pct = min(100, net * 10)
        self._bar_net.set_value(net_pct, net_str)
        gpu = snap["gpu"]
        if gpu >= 0: self._bar_gpu.set_value(gpu, f"{gpu:.0f}%")
        else: self._bar_gpu.set_value(0, "N/A")
        tmp = snap["tmp"]
        if tmp >= 0:
            tmp_pct = min(100, (tmp / 100) * 100)
            self._bar_tmp.set_value(tmp_pct, f"{tmp:.0f}°C")
        else: self._bar_tmp.set_value(0, "N/A")
        try:
            boot_t  = psutil.boot_time()
            elapsed = time.time() - boot_t
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            self._uptime_lbl.setText(f"UPTIME {h:02d}:{m:02d}")
        except Exception:
            self._uptime_lbl.setText("UPTIME --:--")
        try:
            proc_count = len(psutil.pids())
            self._proc_lbl.setText(f"PROCS {proc_count}")
        except Exception:
            self._proc_lbl.setText("PROCS --")

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(64)
        w.setStyleSheet(f"background: {C.DARK}; border-bottom: 1px solid {C.BORDER};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(20, 0, 20, 0)

        def _badge(txt, color=C.TEXT_MED):
            l = QLabel(txt)
            l.setFont(QFont("Plus Jakarta Sans", 9, QFont.Weight.Bold))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_badge("ANDROMEDA", C.PRI))
        lay.addStretch()

        mid = QVBoxLayout(); mid.setSpacing(2)
        title = QLabel("ANDROMEDA")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Plus Jakarta Sans", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.WHITE}; background: transparent; letter-spacing: 2px;")
        mid.addWidget(title)
        sub = QLabel("Sovereign Enterprise Autopilot")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont("JetBrains Mono", 8))
        sub.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent; letter-spacing: 4px; text-transform: uppercase;")
        mid.addWidget(sub)
        lay.addLayout(mid)
        lay.addStretch()

        right_col = QVBoxLayout(); right_col.setSpacing(2)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(QFont("JetBrains Mono", 15, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont("JetBrains Mono", 8))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        lay.addLayout(right_col)
        return w

    def _tick_clock(self):
        self._clock_lbl.setText(time.strftime("%H:%M:%S"))
        self._date_lbl.setText(time.strftime("%a %d %b %Y"))

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_LEFT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-right: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 16, 12, 16)
        lay.setSpacing(8)

        hdr = QLabel("LIVE TELEMETRY")
        hdr.setFont(QFont("JetBrains Mono", 9, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border-bottom: 1px solid {C.BORDER}; padding-bottom: 6px;")
        lay.addWidget(hdr)
        lay.addSpacing(4)

        self._bar_cpu = MetricBar("CPU", C.PRI)
        self._bar_mem = MetricBar("MEM", C.ACC)
        self._bar_net = MetricBar("NET", C.GREEN)
        self._bar_gpu = MetricBar("GPU", C.ACC2)
        self._bar_tmp = MetricBar("TMP", C.MUTED_C)

        for bar in [self._bar_cpu, self._bar_mem, self._bar_net, self._bar_gpu, self._bar_tmp]:
            lay.addWidget(bar)

        lay.addSpacing(8)

        info_panel = QWidget()
        info_panel.setStyleSheet(f"background: {C.PANEL}; border: 1px solid {C.BORDER}; border-radius: 6px;")
        ip_lay = QVBoxLayout(info_panel)
        ip_lay.setContentsMargins(10, 8, 10, 8)
        ip_lay.setSpacing(4)

        self._uptime_lbl = QLabel("UPTIME --:--")
        self._uptime_lbl.setFont(QFont("JetBrains Mono", 9, QFont.Weight.Bold))
        self._uptime_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
        ip_lay.addWidget(self._uptime_lbl)

        self._proc_lbl = QLabel("PROCS --")
        self._proc_lbl.setFont(QFont("JetBrains Mono", 8))
        self._proc_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        ip_lay.addWidget(self._proc_lbl)

        os_name = {"Windows": "WIN", "Darwin": "macOS", "Linux": "LINUX"}.get(_OS, _OS.upper())
        os_lbl = QLabel(f"OS {os_name}")
        os_lbl.setFont(QFont("JetBrains Mono", 8))
        os_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent; border: none;")
        ip_lay.addWidget(os_lbl)

        lay.addWidget(info_panel)
        lay.addStretch()

        for txt, col in [("QWEN MODEL\nACTIVE", C.PRI), ("ZERO-TRUST\nSECURED", C.GREEN), ("HIVEMIND\nSYNCED", C.ACC)]:
            lbl = QLabel(txt)
            lbl.setFont(QFont("JetBrains Mono", 8, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {col}; background: {C.PANEL}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 6px;")
            lay.addWidget(lbl)

        return w

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-left: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        def _sec(txt):
            l = QLabel(f"// {txt}")
            l.setFont(QFont("JetBrains Mono", 9, QFont.Weight.Bold))
            l.setStyleSheet(f"color: {C.PRI}; background: transparent;")
            return l

        lay.addWidget(_sec("SYSTEM LOGS"))
        self._log = LogWidget()
        lay.addWidget(self._log, stretch=1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 4px 0;")
        lay.addWidget(sep)

        lay.addWidget(_sec("SECURE DROPZONE"))
        self._drop_zone = FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._drop_zone)

        self._file_hint = QLabel("Awaiting Payload. Zero bytes leaked.")
        self._file_hint.setFont(QFont("JetBrains Mono", 8))
        self._file_hint.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._file_hint.setWordWrap(True)
        lay.addWidget(self._file_hint)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER}; margin: 4px 0;")
        lay.addWidget(sep2)

        lay.addWidget(_sec("ORCHESTRATION PROMPT"))
        lay.addLayout(self._build_input_row())

        self._mute_btn = QPushButton("🎙 ACOUSTIC SENSOR ACTIVE")
        self._mute_btn.setFixedHeight(36)
        self._mute_btn.setFont(QFont("JetBrains Mono", 9, QFont.Weight.Bold))
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._style_mute_btn()
        lay.addWidget(self._mute_btn)

        fs_btn = QPushButton("⛶ FULLSCREEN [F11]")
        fs_btn.setFixedHeight(30)
        fs_btn.setFont(QFont("JetBrains Mono", 8))
        fs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fs_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 4px;
            }}
            QPushButton:hover {{ color: {C.PRI}; border: 1px solid {C.PRI}; }}
        """)
        fs_btn.clicked.connect(self._toggle_fullscreen)
        lay.addWidget(fs_btn)

        cfg_btn = QPushButton("⚙ CONFIGURE SYSTEM")
        cfg_btn.setFixedHeight(30)
        cfg_btn.setFont(QFont("JetBrains Mono", 8))
        cfg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cfg_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 4px;
            }}
            QPushButton:hover {{ color: {C.ACC2}; border: 1px solid {C.ACC2}; }}
        """)
        cfg_btn.clicked.connect(self._show_config)
        lay.addWidget(cfg_btn)

        return w

    def _build_input_row(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(8)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Assign Andromeda tasks...")
        self._input.setFont(QFont("Plus Jakarta Sans", 10))
        self._input.setFixedHeight(36)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {C.PANEL}; color: {C.WHITE};
                border: 1px solid {C.BORDER}; border-radius: 6px; padding: 4px 10px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input)

        send = QPushButton("▸")
        send.setFixedSize(36, 36)
        send.setFont(QFont("Plus Jakarta Sans", 14, QFont.Weight.Bold))
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(f"""
            QPushButton {{
                background: {C.PRI}; color: {C.BG};
                border: none; border-radius: 6px;
            }}
            QPushButton:hover {{ background: {C.PRI_DIM}; color: {C.WHITE}; }}
        """)
        send.clicked.connect(self._send)
        row.addWidget(send)
        return row

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(28)
        w.setStyleSheet(f"background: {C.DARK}; border-top: 1px solid {C.BORDER};")
        lay = QHBoxLayout(w); lay.setContentsMargins(20, 0, 20, 0)

        def _fl(txt, color=C.TEXT_DIM):
            l = QLabel(txt); l.setFont(QFont("JetBrains Mono", 8))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_fl("[F4] Mute Sensor · [F11] Fullscreen"))
        lay.addStretch()
        lay.addWidget(_fl("Sovereign Node Orchestration · ANDROMEDA AUTOPILOT · ENCRYPTED", C.PRI_DIM))
        lay.addStretch()
        lay.addWidget(_fl("© GSP / METEOR GROUP", C.PRI))
        return w

    def _on_file_selected(self, path: str):
        self._current_file = path
        p    = Path(path)
        cat  = _file_category(p)
        icon, _ = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size = _fmt_size(p.stat().st_size)
        self._file_hint.setText(f"{icon} {p.name} · {size} · Awaiting instruction")
        self._log.append_log(f"FILE: {p.name} ({size}) secured in sandbox")
        if self.on_text_command:
            msg = (
                f"[FILE_UPLOADED] path={path} | name={p.name} | "
                f"type={p.suffix.lstrip('.')} | size={size} | "
                f"Briefly tell the user you have secured '{p.name}' in the local sandbox "
                f"and ask what they'd like to do with it."
            )
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def _toggle_mute(self):
        self._muted = not self._muted
        self.hud.muted = self._muted
        self._style_mute_btn()
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Acoustic Sensor muted.")
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Acoustic Sensor active.")

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setText("🔇 ACOUSTIC SENSOR MUTED")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.PANEL}; color: {C.MUTED_C};
                    border: 1px solid {C.MUTED_C}; border-radius: 6px;
                }}
            """)
        else:
            self._mute_btn.setText("🎙 ACOUSTIC SENSOR ACTIVE")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.PANEL}; color: {C.GREEN};
                    border: 1px solid {C.GREEN_D}; border-radius: 6px;
                }}
                QPushButton:hover {{ background: {C.GREEN_D}; color: {C.WHITE}; }}
            """)

    def _send(self):
        txt = self._input.text().strip()
        if not txt: return
        self._input.clear()
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _apply_state(self, state: str):
        self.hud.state    = state
        self.hud.speaking = (state == "SPEAKING")

    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return (
                bool(d.get("llm_model")) and
                bool(d.get("stt_engine")) and
                bool(d.get("tts_engine"))
            )
        except Exception:
            return False

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        cw = self.centralWidget()
        ow, oh = 580, 680
        ov.setGeometry((cw.width() - ow) // 2, (cw.height() - oh) // 2, ow, oh)
        ov.done.connect(self._on_setup_done)
        ov.show()
        self._overlay = ov

    def _on_setup_done(self, config_json: str):
        try: cfg = json.loads(config_json)
        except Exception: cfg = {}
        os.makedirs(CONFIG_DIR, exist_ok=True)
        API_FILE.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        self._apply_state("LISTENING")
        llm = cfg.get("llm_model", "")
        stt = cfg.get("stt_engine", "")
        tts = cfg.get("tts_engine", "")
        self._log.append_log(f"SYS: Initialized. LLM={llm} | STT={stt} | TTS={tts}")

    def _show_config(self):
        if self._overlay and self._overlay.isVisible(): return
        current: dict = {}
        try: current = json.loads(API_FILE.read_text(encoding="utf-8"))
        except Exception: pass
        ov = SetupOverlay(self.centralWidget(), initial=current, mode="config")
        cw = self.centralWidget()
        ow, oh = 580, 680
        ov.setGeometry((cw.width() - ow) // 2, (cw.height() - oh) // 2, ow, oh)
        ov.done.connect(self._on_config_done)
        ov.show()
        self._overlay = ov

    def _on_config_done(self, config_json: str):
        try: cfg = json.loads(config_json)
        except Exception: cfg = {}
        os.makedirs(CONFIG_DIR, exist_ok=True)
        API_FILE.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        llm = cfg.get("llm_model", "")
        stt = cfg.get("stt_engine", "")
        tts = cfg.get("tts_engine", "")
        self._log.append_log(f"SYS: Config updated. LLM={llm} | STT={stt} | TTS={tts}")
        if self._on_reconfigure_cb:
            self._on_reconfigure_cb(cfg)


class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass


class JarvisUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        self._win.show()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool: return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted: self._win._toggle_mute()

    @property
    def current_file(self) -> str | None: return self._win._drop_zone.current_file()

    @property
    def on_text_command(self): return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb): self._win.on_text_command = cb

    @property
    def on_reconfigure(self): return self._win._on_reconfigure_cb

    @on_reconfigure.setter
    def on_reconfigure(self, cb): self._win._on_reconfigure_cb = cb

    def set_state(self, state: str): self._win._state_sig.emit(state)

    def write_log(self, text: str): self._win._log_sig.emit(text)

    def show_startup_panel(self) -> None: self._win._startup_sig.emit("show", "")

    def mark_startup_ready(self, key: str, error: bool = False) -> None:
        self._win._startup_sig.emit("error" if error else "ready", key)

    def set_startup_status(self, text: str) -> None: self._win._startup_sig.emit("status", text)

    def hide_startup_panel(self) -> None: self._win._startup_sig.emit("hide", "")

    def wait_for_api_key(self):
        while not self._win._ready: time.sleep(0.1)

    def start_speaking(self): self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted: self.set_state("LISTENING")