DARK_STYLESHEET = """
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", "Malgun Gothic", sans-serif;
    font-size: 10pt;
}
QMainWindow {
    background-color: #1e1e2e;
}
QGroupBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px 8px 8px 8px;
    font-weight: bold;
    font-size: 10pt;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    color: #89b4fa;
}
QLabel {
    color: #cdd6f4;
    background: transparent;
}
QPushButton {
    background-color: #45475a;
    color: #cdd6f4;
    border: 1px solid #585b70;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: bold;
    min-height: 30px;
}
QPushButton:hover {
    background-color: #585b70;
    border-color: #89b4fa;
}
QPushButton:pressed {
    background-color: #89b4fa;
    color: #1e1e2e;
}
QPushButton:disabled {
    background-color: #313244;
    color: #6c7086;
    border-color: #45475a;
}
QPushButton#btnConnect {
    background-color: #a6e3a1;
    color: #1e1e2e;
    border: none;
}
QPushButton#btnDisconnect, QPushButton#btnStop {
    background-color: #f38ba8;
    color: #1e1e2e;
    border: none;
}
QPushButton#btnRun {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
}
QPushButton#btnWarn {
    background-color: #fab387;
    color: #1e1e2e;
    border: none;
}
QComboBox, QDoubleSpinBox {
    background-color: #45475a;
    color: #cdd6f4;
    border: 1px solid #585b70;
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 100px;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
    border: 1px solid #585b70;
}
QPlainTextEdit {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
}
QProgressBar {
    background-color: #181825;
    border: 1px solid #45475a;
    border-radius: 6px;
    text-align: center;
    min-height: 24px;
}
QProgressBar::chunk {
    background-color: #fab387;
    border-radius: 4px;
}
QStatusBar {
    background-color: #181825;
    color: #a6adc8;
    border-top: 1px solid #45475a;
}
QSplitter::handle {
    background-color: #45475a;
    border-radius: 1px;
}
QSplitter::handle:hover {
    background-color: #89b4fa;
}
QSplitter::handle:pressed {
    background-color: #b4d0fb;
}
QSplitter::handle:horizontal {
    width: 6px;
    margin: 0 2px;
}
QSplitter::handle:vertical {
    height: 6px;
    margin: 2px 0;
}
"""
