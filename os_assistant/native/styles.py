"""Aura native desktop stylesheet."""

DARK_THEME = """
* {
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
    color: #d9e2ec;
}

QMainWindow, QWidget#central {
    background-color: #080b10;
}

QWidget#sidebar {
    background-color: #0d1218;
    border-right: 1px solid rgba(125, 211, 252, 0.14);
}

QLabel#logo-text {
    font-size: 22px;
    font-weight: 800;
    letter-spacing: 0px;
    color: #67e8f9;
}

QLabel#logo-sub {
    font-size: 11px;
    color: #7dd3fc;
}

QPushButton[class="nav-btn"] {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 10px 12px;
    text-align: left;
    color: #9fb0c0;
    font-weight: 600;
}

QPushButton[class="nav-btn"]:hover {
    background: rgba(20, 184, 166, 0.10);
    border-color: rgba(45, 212, 191, 0.18);
    color: #ccfbf1;
}

QPushButton[class="nav-btn"][active="true"] {
    background: rgba(6, 182, 212, 0.14);
    border-color: rgba(103, 232, 249, 0.30);
    color: #67e8f9;
}

QLabel[class="panel-title"] {
    font-size: 22px;
    font-weight: 800;
    color: #eef6ff;
}

QFrame[class="status-tile"] {
    background-color: #101820;
    border: 1px solid rgba(125, 211, 252, 0.16);
    border-radius: 8px;
}

QLabel[class="tile-label"] {
    color: #7b8da0;
    font-size: 10px;
    font-weight: 700;
}

QLabel[class="tile-value"] {
    color: #dff7ff;
    font-size: 13px;
    font-weight: 700;
}

QScrollArea#chatScroll {
    background: transparent;
    border: none;
}

QWidget#chatContainer {
    background: transparent;
}

QFrame[class="msg-user"] {
    background-color: rgba(6, 182, 212, 0.13);
    border: 1px solid rgba(103, 232, 249, 0.22);
    border-radius: 8px;
    padding: 12px 14px;
}

QFrame[class="msg-thought"], QFrame[class="msg-action"] {
    background-color: #101820;
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: 8px;
    padding: 12px 14px;
}

QFrame[class="msg-error"] {
    background-color: rgba(239, 68, 68, 0.11);
    border: 1px solid rgba(248, 113, 113, 0.28);
    border-radius: 8px;
    padding: 12px 14px;
}

QFrame[class="msg-success"] {
    background-color: rgba(34, 197, 94, 0.11);
    border: 1px solid rgba(74, 222, 128, 0.26);
    border-radius: 8px;
    padding: 12px 14px;
}

QLabel[class="msg-label"] {
    color: #67e8f9;
    font-size: 11px;
    font-weight: 800;
}

QLabel[class="msg-text"] {
    color: #d1dde8;
    line-height: 1.45;
}

QLabel[class="msg-step"] {
    color: #758598;
    font-size: 10px;
}

QTextEdit#taskInput {
    background-color: #101820;
    border: 1px solid rgba(125, 211, 252, 0.18);
    border-radius: 8px;
    padding: 10px 12px;
    color: #eef6ff;
    font-size: 14px;
    selection-background-color: rgba(20, 184, 166, 0.35);
}

QTextEdit#taskInput:focus {
    border-color: rgba(103, 232, 249, 0.65);
    background-color: #121d26;
}

QPushButton#btnSend {
    background-color: #06b6d4;
    border: none;
    border-radius: 8px;
    color: #031217;
    font-weight: 900;
    min-width: 40px;
}

QPushButton#btnSend:hover {
    background-color: #22d3ee;
}

QPushButton#btnSend:pressed {
    background-color: #0891b2;
}

QPushButton[class="ctrl-btn"] {
    background-color: #111a23;
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 8px;
    padding: 7px 14px;
    color: #d1dde8;
    font-weight: 700;
}

QPushButton[class="ctrl-btn"]:hover {
    background-color: #172433;
    border-color: rgba(125, 211, 252, 0.32);
}

QPushButton[class="ctrl-btn"]:checked {
    background-color: rgba(34, 197, 94, 0.16);
    border-color: rgba(74, 222, 128, 0.42);
    color: #86efac;
}

QPushButton#btnStop {
    border-color: rgba(248, 113, 113, 0.34);
    color: #f87171;
}

QPushButton#btnStop:hover {
    background-color: rgba(239, 68, 68, 0.14);
}

QLabel#screenLabel {
    background-color: #05080c;
    border: 1px solid rgba(125, 211, 252, 0.18);
    border-radius: 8px;
    color: #758598;
}

QPushButton#btnLive {
    background-color: rgba(239, 68, 68, 0.13);
    border: 1px solid rgba(248, 113, 113, 0.34);
    border-radius: 8px;
    padding: 7px 14px;
    color: #f87171;
    font-weight: 800;
}

QPushButton#btnLive:hover {
    background-color: rgba(239, 68, 68, 0.20);
}

QPushButton#btnLive[active="true"] {
    background-color: rgba(34, 197, 94, 0.16);
    border-color: rgba(74, 222, 128, 0.42);
    color: #86efac;
}

QSlider::groove:horizontal {
    background: #172433;
    height: 4px;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #67e8f9;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QSlider::sub-page:horizontal {
    background: #14b8a6;
    border-radius: 2px;
}

QFrame#statusBar {
    background-color: #101820;
    border: 1px solid rgba(125, 211, 252, 0.14);
    border-radius: 8px;
}

QLabel#statusDot {
    color: #22c55e;
    font-size: 9px;
}

QLabel#statusLabel {
    font-weight: 800;
    font-size: 12px;
    color: #eef6ff;
}

QLabel#statusDetail {
    color: #7b8da0;
    font-size: 11px;
}

QDialog#confirmDialog {
    background-color: #101820;
    border: 1px solid rgba(125, 211, 252, 0.20);
    border-radius: 8px;
}

QPushButton#btnApprove {
    background-color: rgba(34, 197, 94, 0.16);
    border: 1px solid rgba(74, 222, 128, 0.34);
    border-radius: 8px;
    padding: 8px 24px;
    color: #86efac;
    font-weight: 800;
}

QPushButton#btnApprove:hover {
    background-color: rgba(34, 197, 94, 0.24);
}

QPushButton#btnDeny {
    background-color: rgba(239, 68, 68, 0.14);
    border: 1px solid rgba(248, 113, 113, 0.34);
    border-radius: 8px;
    padding: 8px 24px;
    color: #f87171;
    font-weight: 800;
}

QPushButton#btnDeny:hover {
    background-color: rgba(239, 68, 68, 0.22);
}

QLabel#coordsLabel {
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 11px;
    color: #7b8da0;
}

QScrollBar:vertical {
    background: transparent;
    width: 7px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: rgba(125, 211, 252, 0.28);
    border-radius: 3px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(125, 211, 252, 0.48);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
    height: 0;
}

QPushButton[class="quick-btn"] {
    background-color: #101820;
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: 8px;
    padding: 10px 14px;
    color: #d1dde8;
    font-size: 12px;
    font-weight: 700;
}

QPushButton[class="quick-btn"]:hover {
    background-color: rgba(6, 182, 212, 0.11);
    border-color: rgba(103, 232, 249, 0.28);
    color: #e0fbff;
}

QSplitter::handle {
    background: rgba(125, 211, 252, 0.14);
    width: 1px;
}
"""
