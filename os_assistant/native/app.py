"""
OS Assistant — Native PyQt6 Desktop Application
Main window with Chat + Live Screen side by side.
"""
import sys
import os
import threading
import time
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QScrollArea, QFrame, QSplitter,
    QSlider, QSystemTrayIcon, QMenu, QDialog, QDialogButtonBox,
    QStyle,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize, QThread
from PyQt6.QtGui import QPixmap, QImage, QIcon, QKeySequence, QShortcut, QFont

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.core import AgentCore
from agent.screen import ScreenCapture
from config import Config
from native.styles import DARK_THEME


# ── Signal Bridge (thread-safe UI updates) ──────────────────
class SignalBridge(QObject):
    new_message = pyqtSignal(str, str, int)  # type, text, step
    screenshot = pyqtSignal(object)           # QPixmap
    status_changed = pyqtSignal(str, str)     # label, detail
    confirm_needed = pyqtSignal(str)          # message
    task_done = pyqtSignal(str)               # summary
    wake_word_detected = pyqtSignal()         # triggers STT

# ── QThread Workers (Prevents GIL UI Starvation) ─────────────
class AgentTaskWorker(QThread):
    def __init__(self, agent, task, live_mode, signals):
        super().__init__()
        self.agent = agent
        self.task = task
        self.live_mode = live_mode
        self.signals = signals

    def run(self):
        result = self.agent.execute_task(self.task, live_mode=self.live_mode)
        if not result.get("success"):
            self.signals.new_message.emit("error", result.get("error", "Task failed to start"), 0)

class ListenWorker(QThread):
    def __init__(self, agent, signals, app_ref):
        super().__init__()
        self.agent = agent
        self.signals = signals
        self.app_ref = app_ref

    def run(self):
        res = self.agent.hardware.listen(duration=5.0, offline=True)
        if res.get("success") and res.get("text"):
            task = res["text"]
            self.signals.new_message.emit("user", f"Heard: {task}", 0)
            # Use QTimer to delay the send task back on the main thread
            QTimer.singleShot(500, lambda: self.app_ref._send_task(task))
        else:
            self.signals.status_changed.emit("Ready", "Awaiting your command")
            if res.get("error"):
                self.signals.new_message.emit("error", res["error"], 0)
            else:
                self.signals.new_message.emit("thought", "No speech detected.", 0)


# ── Confirmation Dialog ─────────────────────────────────────
class ConfirmDialog(QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚠️ Confirmation Required")
        self.setFixedSize(420, 180)
        self.setObjectName("confirmDialog")
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        icon = QLabel("⚠️")
        icon.setFont(QFont("Segoe UI", 28))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        msg = QLabel(message)
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(msg)

        btn_layout = QHBoxLayout()
        self.btn_deny = QPushButton("Deny")
        self.btn_deny.setObjectName("btnDeny")
        self.btn_deny.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_deny)

        self.btn_approve = QPushButton("Approve")
        self.btn_approve.setObjectName("btnApprove")
        self.btn_approve.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_approve)
        layout.addLayout(btn_layout)


# ── Main Window ─────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aura")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        self.signals = SignalBridge()
        self.agent = AgentCore(event_callback=self._agent_event)
        self.sc = ScreenCapture()
        self.is_streaming = False
        self.stream_fps = 3
        self.stream_timer = QTimer()
        self.stream_timer.timeout.connect(self._capture_frame)
        self.stream_orig_w = 1920
        self.stream_orig_h = 1080

        # Connect signals
        self.signals.new_message.connect(self._add_message)
        self.signals.status_changed.connect(self._set_status)
        self.signals.confirm_needed.connect(self._show_confirm)
        self.signals.task_done.connect(self._on_task_done)
        self.signals.screenshot.connect(self._update_screen)
        self.signals.wake_word_detected.connect(self._on_wake_word)

        self._build_ui()
        self.setStyleSheet(DARK_THEME)
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self._set_status("Ready", "Awaiting your command")

        # Start wake word listener in background
        self.agent.hardware.start_wake_word_listener(
            on_wake=lambda: self.signals.wake_word_detected.emit()
        )

    # ── Build UI ────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ─ Sidebar ─
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(12, 16, 12, 16)
        sb_layout.setSpacing(6)

        logo = QLabel("AURA")
        logo.setObjectName("logo-text")
        sb_layout.addWidget(logo)
        sub = QLabel("Jarvis-style Desktop AI")
        sub.setObjectName("logo-sub")
        sb_layout.addWidget(sub)
        sb_layout.addSpacing(20)

        self.nav_btns = {}
        for name, icon_text in [("Command", "💬"), ("Screen", "🖥️"),
                                ("Lessons", "🧠"), ("Settings", "⚙️")]:
            btn = QPushButton(f"  {icon_text}  {name}")
            btn.setProperty("class", "nav-btn")
            btn.setProperty("active", name == "Command")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, n=name: self._switch_panel(n))
            sb_layout.addWidget(btn)
            self.nav_btns[name] = btn

        sb_layout.addStretch()

        # Status indicator
        status_frame = QFrame()
        status_frame.setObjectName("statusBar")
        sl = QHBoxLayout(status_frame)
        sl.setContentsMargins(8, 6, 8, 6)
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        sl.addWidget(self.status_dot)
        sv = QVBoxLayout()
        sv.setSpacing(0)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        sv.addWidget(self.status_label)
        self.status_detail = QLabel("Awaiting your command")
        self.status_detail.setObjectName("statusDetail")
        sv.addWidget(self.status_detail)
        sl.addLayout(sv)
        sl.addStretch()
        sb_layout.addWidget(status_frame)

        root.addWidget(sidebar)

        # ─ Content Stack ─
        self.panels = {}
        self.panel_stack = QWidget()
        stack_layout = QVBoxLayout(self.panel_stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)

        # Chat Panel
        self.panels["Command"] = self._build_chat_panel()
        stack_layout.addWidget(self.panels["Command"])

        # Screen Panel
        self.panels["Screen"] = self._build_screen_panel()
        self.panels["Screen"].hide()
        stack_layout.addWidget(self.panels["Screen"])

        # Lessons Panel
        self.panels["Lessons"] = self._build_lessons_panel()
        self.panels["Lessons"].hide()
        stack_layout.addWidget(self.panels["Lessons"])

        # Settings Panel
        self.panels["Settings"] = self._build_settings_panel()
        self.panels["Settings"].hide()
        stack_layout.addWidget(self.panels["Settings"])

        root.addWidget(self.panel_stack)

    # ── Chat Panel ──────────────────────────────────────────
    def _build_chat_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Aura Command")
        title.setProperty("class", "panel-title")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Operational status strip
        status_strip = QHBoxLayout()
        status_strip.setSpacing(10)
        for label, value in [
            ("Brain", Config.AI_PROVIDER.upper()),
            ("Mode", "Desktop Control"),
            ("Memory", "Local + Long-term"),
        ]:
            status_strip.addWidget(self._build_status_tile(label, value))
        layout.addLayout(status_strip)

        # Messages scroll
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setObjectName("chatScroll")
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_container = QWidget()
        self.chat_container.setObjectName("chatContainer")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.setSpacing(8)

        # Welcome
        welcome = QLabel("Tell me what to do on your computer.\n"
                         "I will inspect, act, verify, and report.")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome.setStyleSheet("color: #6b7280; padding: 40px; font-size: 14px;")
        self.welcome_label = welcome
        self.chat_layout.addWidget(welcome)

        self.chat_scroll.setWidget(self.chat_container)
        layout.addWidget(self.chat_scroll, 1)

        # Quick actions
        qa_layout = QHBoxLayout()
        for text, task in [("📝 Notepad", "Open Notepad and write Hello World"),
                           ("🧮 Calculator", "Open the calculator app"),
                           ("🌐 Web Search", "Open Chrome and search for today's weather"),
                           ("📸 Screenshot", "Take a screenshot and save to desktop")]:
            btn = QPushButton(text)
            btn.setProperty("class", "quick-btn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, t=task: self._send_task(t))
            qa_layout.addWidget(btn)
        layout.addLayout(qa_layout)

        # Live mode toggle
        mode_row = QHBoxLayout()
        self.btn_live_mode = QPushButton("⚡ Live Mode: OFF")
        self.btn_live_mode.setProperty("class", "ctrl-btn")
        self.btn_live_mode.setCheckable(True)
        self.btn_live_mode.setToolTip("Live mode: no disk I/O — faster for gaming/trading tasks")
        self.btn_live_mode.clicked.connect(self._toggle_live_mode)
        mode_row.addWidget(self.btn_live_mode)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # Input row
        input_row = QHBoxLayout()
        self.task_input = QTextEdit()
        self.task_input.setObjectName("taskInput")
        self.task_input.setPlaceholderText("Give Aura a command... English, Bangla, or Hindi")
        self.task_input.setMaximumHeight(50)
        self.task_input.installEventFilter(self)
        input_row.addWidget(self.task_input, 1)

        self.btn_send = QPushButton("➤")
        self.btn_send.setObjectName("btnSend")
        self.btn_send.setFixedSize(44, 44)
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.clicked.connect(self._on_send)
        input_row.addWidget(self.btn_send)
        layout.addLayout(input_row)

        # Task controls (hidden by default)
        ctrl_row = QHBoxLayout()
        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setProperty("class", "ctrl-btn")
        self.btn_pause.clicked.connect(lambda: self.agent.pause())
        ctrl_row.addWidget(self.btn_pause)

        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setProperty("class", "ctrl-btn")
        self.btn_stop.clicked.connect(lambda: self.agent.stop())
        ctrl_row.addWidget(self.btn_stop)
        ctrl_row.addStretch()

        self.ctrl_widget = QWidget()
        self.ctrl_widget.setLayout(ctrl_row)
        self.ctrl_widget.hide()
        layout.addWidget(self.ctrl_widget)

        return panel

    # ── Screen Panel ────────────────────────────────────────
    def _build_status_tile(self, label, value):
        tile = QFrame()
        tile.setProperty("class", "status-tile")
        tl = QVBoxLayout(tile)
        tl.setContentsMargins(12, 10, 12, 10)
        tl.setSpacing(2)

        label_widget = QLabel(label)
        label_widget.setProperty("class", "tile-label")
        tl.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setProperty("class", "tile-value")
        value_widget.setWordWrap(True)
        tl.addWidget(value_widget)
        return tile

    def _build_screen_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Live Screen Control")
        title.setProperty("class", "panel-title")
        header.addWidget(title)
        header.addStretch()

        self.btn_snapshot = QPushButton("📷 Snapshot")
        self.btn_snapshot.setProperty("class", "ctrl-btn")
        self.btn_snapshot.clicked.connect(self._take_snapshot)
        header.addWidget(self.btn_snapshot)

        self.btn_live = QPushButton("🔴 Go Live")
        self.btn_live.setObjectName("btnLive")
        self.btn_live.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_live.clicked.connect(self._toggle_stream)
        header.addWidget(self.btn_live)
        layout.addLayout(header)

        # Controls bar
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("FPS:"))
        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setRange(1, 15)
        self.fps_slider.setValue(3)
        self.fps_slider.setFixedWidth(100)
        self.fps_slider.valueChanged.connect(self._fps_changed)
        ctrl.addWidget(self.fps_slider)
        self.fps_label = QLabel("3")
        ctrl.addWidget(self.fps_label)
        ctrl.addSpacing(20)
        self.coords_label = QLabel("X: —  Y: —")
        self.coords_label.setObjectName("coordsLabel")
        ctrl.addWidget(self.coords_label)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        # Screen display
        self.screen_label = QLabel("Click 'Go Live' to start streaming")
        self.screen_label.setObjectName("screenLabel")
        self.screen_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.screen_label.setMinimumHeight(400)
        self.screen_label.setMouseTracking(True)
        self.screen_label.setCursor(Qt.CursorShape.CrossCursor)
        self.screen_label.mousePressEvent = self._screen_clicked
        self.screen_label.mouseMoveEvent = self._screen_mouse_move
        layout.addWidget(self.screen_label, 1)

        # Info bar
        info = QHBoxLayout()
        self.res_label = QLabel("—")
        info.addWidget(self.res_label)
        self.fps_display = QLabel("—")
        self.fps_display.setStyleSheet("color: #a78bfa; font-weight: 600;")
        info.addWidget(self.fps_display)
        self.time_label = QLabel("—")
        info.addWidget(self.time_label)
        info.addStretch()
        layout.addLayout(info)

        return panel

    # ── Lessons Panel ────────────────────────────────────────
    def _build_lessons_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("🧠 Learned Lessons")
        title.setProperty("class", "panel-title")
        header.addWidget(title)
        header.addStretch()

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setProperty("class", "ctrl-btn")
        btn_refresh.clicked.connect(self._refresh_lessons)
        header.addWidget(btn_refresh)

        btn_purge = QPushButton("🗑 Purge Weak")
        btn_purge.setProperty("class", "ctrl-btn")
        btn_purge.clicked.connect(self._purge_weak_lessons)
        header.addWidget(btn_purge)
        layout.addLayout(header)

        # Stats bar
        self.lesson_stats_label = QLabel("Loading...")
        self.lesson_stats_label.setStyleSheet("color: #9ca3af; font-size: 12px;")
        layout.addWidget(self.lesson_stats_label)

        # Lessons scroll
        scroll = QScrollArea()
        scroll.setObjectName("chatScroll")
        scroll.setWidgetResizable(True)
        self.lessons_container = QWidget()
        self.lessons_layout = QVBoxLayout(self.lessons_container)
        self.lessons_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lessons_layout.setSpacing(8)
        scroll.setWidget(self.lessons_container)
        layout.addWidget(scroll, 1)

        # Load initial data
        QTimer.singleShot(500, self._refresh_lessons)
        return panel

    def _refresh_lessons(self):
        """Reload lessons from enrollment engine into UI."""
        # Clear
        while self.lessons_layout.count():
            item = self.lessons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lessons = self.agent.enrollment.get_all_lessons(sort_by="confidence")
        stats = self.agent.enrollment.get_stats()

        self.lesson_stats_label.setText(
            f"Total: {stats['lessons_total']} | "
            f"🤖 AI-written: {stats['ai_written']} | "
            f"📋 Templates: {stats['template_written']} | "
            f"Avg confidence: {stats['avg_confidence']}"
        )

        if not lessons:
            empty = QLabel("No lessons yet. Run some tasks and the agent will learn automatically.")
            empty.setStyleSheet("color: #6b7280; padding: 40px; font-size: 13px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lessons_layout.addWidget(empty)
            return

        for lesson in lessons:
            self.lessons_layout.addWidget(self._make_lesson_card(lesson))

    def _make_lesson_card(self, lesson: dict) -> QFrame:
        frame = QFrame()
        frame.setObjectName("msgFrame")
        frame.setStyleSheet("""
            QFrame#msgFrame {
                background: rgba(30,32,48,0.85);
                border: 1px solid rgba(139,92,246,0.2);
                border-radius: 10px;
                padding: 4px;
            }
        """)
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(12, 8, 12, 8)
        fl.setSpacing(4)

        # Title row
        title_row = QHBoxLayout()
        ai_tag = "🤖" if lesson.get("ai_written") else "📋"
        conf = lesson.get("confidence", 1.0)
        conf_color = "#22c55e" if conf >= 0.8 else "#f59e0b" if conf >= 0.4 else "#ef4444"
        title_lbl = QLabel(f"{ai_tag} {lesson.get('title', 'Lesson')[:70]}")
        title_lbl.setStyleSheet("font-weight: 600; color: #e0e0e8; font-size: 13px;")
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        conf_lbl = QLabel(f"conf: {conf:.2f}")
        conf_lbl.setStyleSheet(f"color: {conf_color}; font-size: 11px; font-weight: 600;")
        title_row.addWidget(conf_lbl)
        fl.addLayout(title_row)

        # Category + task
        meta = QLabel(
            f"📂 {lesson.get('category','?')} | "
            f"🎯 {lesson.get('task','?')[:50]} | "
            f"Used: {lesson.get('used_count', 0)}x"
        )
        meta.setStyleSheet("color: #6b7280; font-size: 11px;")
        fl.addWidget(meta)

        # Lesson content
        content = QLabel(f"💡 {lesson.get('do_differently', '—')[:200]}")
        content.setWordWrap(True)
        content.setStyleSheet("color: #c4b5fd; font-size: 12px; padding-top: 4px;")
        fl.addWidget(content)

        # Delete button
        lid = lesson.get("_id", "")
        if lid:
            btn_row = QHBoxLayout()
            btn_row.addStretch()
            del_btn = QPushButton("Delete")
            del_btn.setStyleSheet(
                "QPushButton { color: #ef4444; background: transparent; "
                "border: 1px solid #ef4444; border-radius: 4px; "
                "padding: 2px 8px; font-size: 11px; } "
                "QPushButton:hover { background: rgba(239,68,68,0.15); }"
            )
            del_btn.clicked.connect(lambda _, l=lid: self._delete_lesson(l))
            btn_row.addWidget(del_btn)
            fl.addLayout(btn_row)

        return frame

    def _delete_lesson(self, lesson_id: str):
        self.agent.enrollment.delete_lesson(lesson_id)
        self._refresh_lessons()

    def _purge_weak_lessons(self):
        removed = self.agent.enrollment.purge_low_confidence(threshold=0.25)
        self._refresh_lessons()
        self._add_message("success", f"Purged {removed} low-confidence lessons.", 0)

    # ── Settings Panel ──────────────────────────────────────
    def _build_settings_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        title = QLabel("Settings")
        title.setProperty("class", "panel-title")
        layout.addWidget(title)

        # ── Agent Info ──
        info_lbl = QLabel("🤖 Agent")
        info_lbl.setStyleSheet("color: #a78bfa; font-weight: 700; font-size: 13px;")
        layout.addWidget(info_lbl)

        for label, value in [
            ("AI Provider", Config.AI_PROVIDER),
            ("Model", getattr(Config, f"{Config.AI_PROVIDER.upper()}_MODEL", "—")),
            ("Resolution", f"{self.sc.get_screen_size()[0]} × {self.sc.get_screen_size()[1]}"),
            ("Version", "v2.0.0 — Native Desktop"),
        ]:
            row = QHBoxLayout()
            l = QLabel(label)
            l.setStyleSheet("color: #9ca3af; font-weight: 500;")
            row.addWidget(l)
            v = QLabel(str(value))
            v.setStyleSheet("color: #e0e0e8; font-weight: 600;")
            row.addWidget(v)
            row.addStretch()
            layout.addLayout(row)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: rgba(255,255,255,0.08);")
        layout.addWidget(sep1)

        # ── Voice (TTS) Controls ──
        voice_lbl = QLabel("🗣️ Voice Output")
        voice_lbl.setStyleSheet("color: #a78bfa; font-weight: 700; font-size: 13px;")
        layout.addWidget(voice_lbl)

        # Enable / Disable toggle row
        voice_row = QHBoxLayout()
        voice_row.addWidget(QLabel("Voice"))
        voice_row.addStretch()
        self.btn_voice_toggle = QPushButton("🔊 ON" if self.agent.tts.is_available() else "❌ Not available")
        self.btn_voice_toggle.setProperty("class", "ctrl-btn")
        self.btn_voice_toggle.setCheckable(True)
        self.btn_voice_toggle.setChecked(True)
        self.btn_voice_toggle.clicked.connect(self._toggle_voice)
        voice_row.addWidget(self.btn_voice_toggle)
        layout.addLayout(voice_row)

        # Rate slider
        rate_row = QHBoxLayout()
        rate_row.addWidget(QLabel("Speed:"))
        self.rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.rate_slider.setRange(100, 280)
        self.rate_slider.setValue(175)
        self.rate_slider.setFixedWidth(140)
        self.rate_lbl = QLabel("175 wpm")
        self.rate_slider.valueChanged.connect(lambda v: (
            self.agent.tts.set_rate(v),
            self.rate_lbl.setText(f"{v} wpm")
        ))
        rate_row.addWidget(self.rate_slider)
        rate_row.addWidget(self.rate_lbl)
        rate_row.addStretch()
        layout.addLayout(rate_row)

        # Voice gender row
        gender_row = QHBoxLayout()
        gender_row.addWidget(QLabel("Voice:"))
        for g in ["Female", "Male"]:
            btn = QPushButton(g)
            btn.setProperty("class", "ctrl-btn")
            btn.clicked.connect(lambda _, gender=g.lower(): self.agent.tts.set_voice(gender))
            gender_row.addWidget(btn)
        btn_test = QPushButton("🔊 Test")
        btn_test.setProperty("class", "ctrl-btn")
        btn_test.clicked.connect(lambda: self.agent.tts.speak("Hello. I am Aura, your Jarvis style desktop assistant. How can I help?"))
        gender_row.addWidget(btn_test)
        gender_row.addStretch()
        layout.addLayout(gender_row)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: rgba(255,255,255,0.08);")
        layout.addWidget(sep2)

        # ── Adaptive Resource Manager Status ──
        arm_lbl = QLabel("⚡ Resource Manager")
        arm_lbl.setStyleSheet("color: #a78bfa; font-weight: 700; font-size: 13px;")
        layout.addWidget(arm_lbl)

        self.arm_profile_lbl = QLabel("Profile: —")
        self.arm_profile_lbl.setStyleSheet("color: #e0e0e8; font-size: 12px;")
        layout.addWidget(self.arm_profile_lbl)

        self.arm_cpu_lbl = QLabel("CPU: — | RAM: —")
        self.arm_cpu_lbl.setStyleSheet("color: #9ca3af; font-size: 12px;")
        layout.addWidget(self.arm_cpu_lbl)

        self.arm_screen_lbl = QLabel("Screen scan: —")
        self.arm_screen_lbl.setStyleSheet("color: #9ca3af; font-size: 12px;")
        layout.addWidget(self.arm_screen_lbl)

        btn_refresh_arm = QPushButton("🔄 Refresh Status")
        btn_refresh_arm.setProperty("class", "ctrl-btn")
        btn_refresh_arm.clicked.connect(self._refresh_arm_status)
        layout.addWidget(btn_refresh_arm)

        # Auto-refresh ARM status every 10 seconds
        self._arm_timer = QTimer()
        self._arm_timer.timeout.connect(self._refresh_arm_status)
        self._arm_timer.start(10000)
        self._refresh_arm_status()  # initial

        layout.addStretch()
        return panel

    def _toggle_voice(self):
        tts = self.agent.tts
        if self.btn_voice_toggle.isChecked():
            tts._enabled = True
            self.btn_voice_toggle.setText("🔊 ON")
            tts.speak("Voice enabled.")
        else:
            tts._enabled = False
            self.btn_voice_toggle.setText("🔇 OFF")

    def _refresh_arm_status(self):
        try:
            s = self.agent.arm.get_status()
            profile = s['profile'].upper()
            colors = {"PERFORMANCE": "#22c55e", "BALANCED": "#f59e0b", "ECO": "#ef4444"}
            c = colors.get(profile, "#e0e0e8")
            heavy = " ⚠️ Heavy app" if s['heavy_app_detected'] else ""
            self.arm_profile_lbl.setText(f"Profile: <span style='color:{c};font-weight:700'>{profile}</span>{heavy}")
            self.arm_profile_lbl.setTextFormat(Qt.TextFormat.RichText)
            self.arm_cpu_lbl.setText(f"CPU: {s['cpu_percent']:.0f}% | RAM: {s['ram_percent']:.0f}%")
            self.arm_screen_lbl.setText(f"Screen scan interval: {s['screen_interval']:.0f}s")
        except Exception:
            pass

    # ── Event Filter (Enter to send) ────────────────────────
    def eventFilter(self, obj, event):
        if obj == self.task_input and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and not event.modifiers():
                self._on_send()
                return True
        return super().eventFilter(obj, event)

    # ── Panel Switching ─────────────────────────────────────
    def _switch_panel(self, name):
        for n, btn in self.nav_btns.items():
            btn.setProperty("active", n == name)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        for n, p in self.panels.items():
            p.setVisible(n == name)

    # ── Send Task ───────────────────────────────────────────
    def _on_send(self):
        text = self.task_input.toPlainText().strip()
        if not text:
            return
        self._send_task(text)

    def _toggle_live_mode(self):
        on = self.btn_live_mode.isChecked()
        self.btn_live_mode.setText("⚡ Live Mode: ON" if on else "⚡ Live Mode: OFF")

    def _send_task(self, task):
        self.task_input.clear()
        if self.welcome_label.isVisible():
            self.welcome_label.hide()

        self._add_message("user", task, 0)
        self.ctrl_widget.show()
        self._set_status("Working", f"Executing: {task[:40]}...")

        # Run agent in background QThread to bypass GIL UI freezing
        live_mode = self.btn_live_mode.isChecked()
        self._task_thread = AgentTaskWorker(self.agent, task, live_mode, self.signals)
        self._task_thread.start()

    def _on_wake_word(self):
        """Called when 'Hey Assistant' is detected."""
        self._switch_panel("Command")
        self._set_status("Listening", "Speak your command...")
        
        # Speak confirmation aloud + UI beep
        self.agent.tts.speak_wake_confirmed()
            
        self._add_message("thought", "🎙️ Listening for command...", 0)
        
        # Start listening in background QThread
        self._listen_thread = ListenWorker(self.agent, self.signals, self)
        self._listen_thread.start()

    # ── Agent Event Callback (from agent thread) ────────────
    def _agent_event(self, event, data):
        if event == "thought":
            self.signals.new_message.emit("thought", data.get("thought", ""), data.get("step", 0))
        elif event == "llm_response":
            self.signals.new_message.emit("thought", data.get("text", ""), data.get("step", 0))
        elif event == "history_update":
            role = data.get("role", "thought")
            msg_type = "thought" if role == "ai" else "user" if role == "user" else "thought"
            self.signals.new_message.emit(msg_type, data.get("text", ""), data.get("step", 0))
        elif event == "action":
            import json
            self.signals.new_message.emit("action", json.dumps(data.get("action", {}), indent=2), data.get("step", 0))
        elif event == "screenshot":
            pass  # handled by live stream
        elif event == "action_result":
            res = data.get("result", {})
            if not res.get("success"):
                self.signals.new_message.emit("error", res.get("error", "Action failed"), data.get("step", 0))
        elif event == "blocked":
            self.signals.new_message.emit("error", f"Blocked: {data.get('reason', '')}", data.get("step", 0))
        elif event == "need_confirmation":
            self.signals.confirm_needed.emit(data.get("message", "Approve this action?"))
        elif event == "task_started":
            self.signals.status_changed.emit("Working", f"Executing: {data.get('task', '')[:40]}...")
        elif event == "task_done":
            self.signals.task_done.emit(data.get("summary", "Done!"))
        elif event == "task_failed":
            self.signals.new_message.emit("error", data.get("summary", "Failed"), 0)
            self.signals.status_changed.emit("Ready", "Awaiting your command")
            self.ctrl_widget.hide()
        elif event == "task_stopped":
            self.signals.status_changed.emit("Ready", "Awaiting your command")
            self.ctrl_widget.hide()
        elif event == "error":
            self.signals.new_message.emit("error", data.get("message", "Error"), 0)
        elif event == "info":
            # Shows lesson learned notifications + anti-hijack etc
            self.signals.new_message.emit("thought", data.get("message", ""), 0)

    # ── UI Update Slots ─────────────────────────────────────
    def _add_message(self, msg_type, text, step):
        frame = QFrame()
        frame.setProperty("class", f"msg-{msg_type}")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(2)

        labels = {"user": "👤 You", "thought": "💭 Thinking", "action": "⚡ Action",
                  "error": "⚠️ Error", "success": "✅ Complete"}
        lbl = QLabel(labels.get(msg_type, msg_type))
        lbl.setProperty("class", "msg-label")
        fl.addWidget(lbl)

        txt = QLabel(text)
        txt.setProperty("class", "msg-text")
        txt.setWordWrap(True)
        txt.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        fl.addWidget(txt)

        if step:
            s = QLabel(f"Step {step}")
            s.setProperty("class", "msg-step")
            fl.addWidget(s)

        self.chat_layout.addWidget(frame)
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()))

    def _set_status(self, label, detail):
        self.status_label.setText(label)
        self.status_detail.setText(detail)
        color = "#22c55e" if label == "Ready" else "#f59e0b" if label == "Working" else "#ef4444"
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 8px;")

    def _show_confirm(self, message):
        dlg = ConfirmDialog(message, self)
        dlg.setStyleSheet(DARK_THEME)
        result = dlg.exec()
        self.agent.confirm(result == QDialog.DialogCode.Accepted)

    def _on_task_done(self, summary):
        self.ctrl_widget.hide()
        self._set_status("Ready", "Awaiting your command")
        self._add_message("success", summary, 0)

    # ── Live Stream ─────────────────────────────────────────
    def _toggle_stream(self):
        if self.is_streaming:
            self.is_streaming = False
            self.stream_timer.stop()
            self.btn_live.setText("🔴 Go Live")
            self.btn_live.setProperty("active", False)
            self.fps_display.setText("—")
        else:
            self.is_streaming = True
            self.stream_timer.start(int(1000 / self.stream_fps))
            self.btn_live.setText("🔴 LIVE")
            self.btn_live.setProperty("active", True)
            self.fps_display.setText(f"{self.stream_fps} FPS")
        self.btn_live.style().unpolish(self.btn_live)
        self.btn_live.style().polish(self.btn_live)

    def _fps_changed(self, val):
        self.stream_fps = val
        self.fps_label.setText(str(val))
        if self.is_streaming:
            self.stream_timer.setInterval(int(1000 / val))
            self.fps_display.setText(f"{val} FPS")

    def _capture_frame(self):
        try:
            import io
            from PIL import Image
            sct = self.sc._get_sct()
            raw = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            self.stream_orig_w, self.stream_orig_h = raw.width, raw.height
            lw, lh = self.screen_label.width(), self.screen_label.height()
            if lw > 0 and lh > 0:
                img.thumbnail((lw, lh), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="BMP")
            buf.seek(0)
            qimg = QImage()
            qimg.loadFromData(buf.read())
            self.screen_label.setPixmap(QPixmap.fromImage(qimg))
            self.res_label.setText(f"{self.stream_orig_w} × {self.stream_orig_h}")
            self.time_label.setText(datetime.now().strftime("%H:%M:%S"))
        except Exception:
            pass

    def _take_snapshot(self):
        try:
            result = self.sc.take_screenshot(save=False)
            import base64
            data = base64.b64decode(result["base64"])
            qimg = QImage()
            qimg.loadFromData(data)
            pix = QPixmap.fromImage(qimg)
            self.screen_label.setPixmap(pix.scaled(
                self.screen_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        except Exception:
            pass

    def _update_screen(self, pixmap):
        self.screen_label.setPixmap(pixmap)

    # ── Screen Interaction ──────────────────────────────────
    def _screen_clicked(self, event):
        if not self.is_streaming:
            return
        pix = self.screen_label.pixmap()
        if not pix:
            return
        # Map click position to real screen coordinates
        lbl_w, lbl_h = self.screen_label.width(), self.screen_label.height()
        pix_w, pix_h = pix.width(), pix.height()
        # Calculate offset (pixmap is centered in label)
        off_x = (lbl_w - pix_w) / 2
        off_y = (lbl_h - pix_h) / 2
        rel_x = event.position().x() - off_x
        rel_y = event.position().y() - off_y
        if rel_x < 0 or rel_y < 0 or rel_x > pix_w or rel_y > pix_h:
            return
        real_x = int((rel_x / pix_w) * self.stream_orig_w)
        real_y = int((rel_y / pix_h) * self.stream_orig_h)

        import pydirectinput
        if event.button() == Qt.MouseButton.RightButton:
            pydirectinput.rightClick(real_x, real_y)
        else:
            pydirectinput.click(real_x, real_y)

    def _screen_mouse_move(self, event):
        pix = self.screen_label.pixmap()
        if not pix or not self.is_streaming:
            self.coords_label.setText("X: —  Y: —")
            return
        lbl_w, lbl_h = self.screen_label.width(), self.screen_label.height()
        pix_w, pix_h = pix.width(), pix.height()
        off_x = (lbl_w - pix_w) / 2
        off_y = (lbl_h - pix_h) / 2
        rel_x = event.position().x() - off_x
        rel_y = event.position().y() - off_y
        if 0 <= rel_x <= pix_w and 0 <= rel_y <= pix_h:
            real_x = int((rel_x / pix_w) * self.stream_orig_w)
            real_y = int((rel_y / pix_h) * self.stream_orig_h)
            self.coords_label.setText(f"X: {real_x}  Y: {real_y}")
        else:
            self.coords_label.setText("X: —  Y: —")

    # ── System Tray ─────────────────────────────────────────
    def setup_tray(self, app):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.windowIcon())
        self.tray.setToolTip("Aura")
        menu = QMenu()
        show_action = menu.addAction("Show")
        show_action.triggered.connect(self.showNormal)
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(app.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.showNormal()
                                    if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    def closeEvent(self, event):
        if hasattr(self, 'tray') and self.tray.isVisible():
            self.hide()
            self.tray.showMessage("Aura", "Running in background", QSystemTrayIcon.MessageIcon.Information, 2000)
            event.ignore()
        else:
            event.accept()


# ── Entry Point ─────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Aura")
    app.setStyle("Fusion")
    app.setWindowIcon(app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

    window = MainWindow()
    window.setup_tray(app)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
