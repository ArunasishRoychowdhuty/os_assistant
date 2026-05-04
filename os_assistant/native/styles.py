"""
OS Assistant — QSS Stylesheet
Premium dark theme with glassmorphism effects.
"""

DARK_THEME = """
/* ── Global ── */
* {
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
    color: #e0e0e8;
}

QMainWindow, QWidget#central {
    background-color: #0a0a10;
}

/* ── Sidebar ── */
QWidget#sidebar {
    background-color: rgba(12, 12, 20, 0.95);
    border-right: 1px solid rgba(255, 255, 255, 0.06);
}

QLabel#logo-text {
    font-size: 16px;
    font-weight: bold;
    color: #a78bfa;
}

QLabel#logo-sub {
    font-size: 10px;
    color: #6b7280;
}

/* ── Nav Buttons ── */
QPushButton.nav-btn {
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    text-align: left;
    color: #9ca3af;
    font-weight: 500;
}

QPushButton.nav-btn:hover {
    background: rgba(139, 92, 246, 0.1);
    color: #c4b5fd;
}

QPushButton.nav-btn[active="true"] {
    background: rgba(139, 92, 246, 0.15);
    color: #a78bfa;
    border-left: 3px solid #a78bfa;
}

/* ── Panel Headers ── */
QLabel.panel-title {
    font-size: 20px;
    font-weight: 700;
    color: #f3f4f6;
    padding: 0;
    margin: 0;
}

/* ── Chat Area ── */
QScrollArea#chatScroll {
    background: transparent;
    border: none;
}

QWidget#chatContainer {
    background: transparent;
}

/* ── Message Bubbles ── */
QFrame.msg-user {
    background: rgba(139, 92, 246, 0.12);
    border: 1px solid rgba(139, 92, 246, 0.2);
    border-radius: 12px;
    padding: 12px 16px;
}

QFrame.msg-assistant {
    background: rgba(20, 20, 35, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    padding: 12px 16px;
}

QFrame.msg-error {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.2);
    border-radius: 12px;
    padding: 12px 16px;
}

QFrame.msg-success {
    background: rgba(34, 197, 94, 0.1);
    border: 1px solid rgba(34, 197, 94, 0.2);
    border-radius: 12px;
    padding: 12px 16px;
}

QLabel.msg-label {
    font-size: 11px;
    font-weight: 600;
    color: #a78bfa;
    margin-bottom: 4px;
}

QLabel.msg-text {
    color: #d1d5db;
    line-height: 1.5;
}

QLabel.msg-step {
    font-size: 10px;
    color: #6b7280;
    margin-top: 4px;
}

/* ── Input Area ── */
QTextEdit#taskInput {
    background: rgba(20, 20, 35, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 12px 16px;
    color: #e0e0e8;
    font-size: 14px;
    selection-background-color: rgba(139, 92, 246, 0.3);
}

QTextEdit#taskInput:focus {
    border-color: rgba(139, 92, 246, 0.5);
}

/* ── Buttons ── */
QPushButton#btnSend {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #7c3aed, stop:1 #a78bfa);
    border: none;
    border-radius: 10px;
    padding: 10px 18px;
    color: white;
    font-weight: 600;
    min-width: 40px;
}

QPushButton#btnSend:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #6d28d9, stop:1 #8b5cf6);
}

QPushButton#btnSend:pressed {
    background: #5b21b6;
}

QPushButton.ctrl-btn {
    background: rgba(30, 30, 50, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 6px 14px;
    color: #d1d5db;
    font-weight: 500;
}

QPushButton.ctrl-btn:hover {
    background: rgba(40, 40, 65, 0.8);
    border-color: rgba(255, 255, 255, 0.2);
}

QPushButton#btnStop {
    border-color: rgba(239, 68, 68, 0.3);
    color: #ef4444;
}

QPushButton#btnStop:hover {
    background: rgba(239, 68, 68, 0.15);
}

/* ── Live Screen ── */
QLabel#screenLabel {
    background: rgba(10, 10, 18, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
}

QPushButton#btnLive {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 8px;
    padding: 6px 14px;
    color: #ef4444;
    font-weight: 600;
}

QPushButton#btnLive:hover {
    background: rgba(239, 68, 68, 0.25);
}

QPushButton#btnLive[active="true"] {
    background: rgba(239, 68, 68, 0.2);
    border-color: #ef4444;
}

/* ── FPS Slider ── */
QSlider::groove:horizontal {
    background: rgba(30, 30, 50, 0.8);
    height: 4px;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #a78bfa;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QSlider::sub-page:horizontal {
    background: rgba(139, 92, 246, 0.5);
    border-radius: 2px;
}

/* ── Status Bar ── */
QFrame#statusBar {
    background: rgba(12, 12, 20, 0.9);
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding: 6px 16px;
}

QLabel#statusDot {
    color: #22c55e;
    font-size: 8px;
}

QLabel#statusLabel {
    font-weight: 600;
    font-size: 12px;
}

QLabel#statusDetail {
    color: #6b7280;
    font-size: 11px;
}

/* ── Confirmation Dialog ── */
QDialog#confirmDialog {
    background: rgba(15, 15, 25, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
}

QPushButton#btnApprove {
    background: rgba(34, 197, 94, 0.2);
    border: 1px solid rgba(34, 197, 94, 0.3);
    border-radius: 8px;
    padding: 8px 24px;
    color: #22c55e;
    font-weight: 600;
}

QPushButton#btnApprove:hover {
    background: rgba(34, 197, 94, 0.3);
}

QPushButton#btnDeny {
    background: rgba(239, 68, 68, 0.2);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 8px;
    padding: 8px 24px;
    color: #ef4444;
    font-weight: 600;
}

QPushButton#btnDeny:hover {
    background: rgba(239, 68, 68, 0.3);
}

/* ── Coords Label ── */
QLabel#coordsLabel {
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 11px;
    color: #6b7280;
}

/* ── Scroll Bars ── */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: rgba(139, 92, 246, 0.3);
    border-radius: 3px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(139, 92, 246, 0.5);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
    height: 0;
}

/* ── Quick Action Buttons ── */
QPushButton.quick-btn {
    background: rgba(20, 20, 35, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 10px 16px;
    color: #d1d5db;
    font-size: 12px;
}

QPushButton.quick-btn:hover {
    background: rgba(139, 92, 246, 0.1);
    border-color: rgba(139, 92, 246, 0.3);
    color: #c4b5fd;
}

/* ── Splitter ── */
QSplitter::handle {
    background: rgba(255, 255, 255, 0.06);
    width: 1px;
}
"""
