# 메인 윈도우에서 반복 사용하는 공통 UI 부품 모음입니다.
import math

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from .config import DEFAULT_BAUDRATE
from .core import ProcessState


# 상단 연결 상태를 점 형태로 보여주는 LED 위젯입니다.
class StatusLED(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._color = QColor("#6c7086")

    # 연결 여부에 따라 LED 색상을 바꿉니다.
    def set_connected(self, connected):
        self._color = QColor("#a6e3a1") if connected else QColor("#f38ba8")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(self._color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 12, 12)
        painter.end()


# 카메라 영상을 비율 유지한 채 표시하는 공용 패널입니다.
class VideoPanel(QLabel):
    def __init__(self, title):
        super().__init__(title)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(920, 620)
        self.setStyleSheet(
            "QLabel { background-color: #11111b; border: 1px solid #45475a; border-radius: 8px; }"
        )

    # 새 프레임을 현재 패널 크기에 맞춰 갱신합니다.
    def set_frame(self, image):
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)


# 포트 선택, 연결/해제, 설정 버튼이 모인 상단 제어 바입니다.
class SerialBar(QWidget):
    connect_requested = pyqtSignal(str)
    disconnect_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 6, 12, 6)
        outer.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(10)

        self.led = StatusLED()
        row.addWidget(self.led)
        row.addWidget(QLabel("Port:"))

        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(160)
        row.addWidget(self.port_combo)

        self.refresh_button = QPushButton("⟳")
        self.refresh_button.setFixedWidth(36)
        row.addWidget(self.refresh_button)

        row.addWidget(QLabel(f"Baud: {DEFAULT_BAUDRATE}"))

        self.status_label = QLabel("Arduino Disconnected")
        self.status_label.setStyleSheet("font-weight: bold;")
        row.addWidget(self.status_label)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("btnConnect")
        row.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setObjectName("btnDisconnect")
        self.disconnect_button.setEnabled(False)
        row.addWidget(self.disconnect_button)

        self.settings_button = QPushButton("Settings")
        row.addWidget(self.settings_button)

        row.addStretch()
        outer.addLayout(row)

        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.connect_button.clicked.connect(self._emit_connect)
        self.disconnect_button.clicked.connect(self.disconnect_requested.emit)
        self.settings_button.clicked.connect(self.settings_requested.emit)

    # 현재 콤보박스에서 선택된 포트를 connect 시그널로 전달합니다.
    def _emit_connect(self):
        port = self.port_combo.currentData()
        if port:
            self.connect_requested.emit(port)

    # 포트 목록을 새로 반영하고, 이전 선택이 있으면 최대한 유지합니다.
    def set_ports(self, ports):
        current = self.port_combo.currentData()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        if not ports:
            self.port_combo.addItem("No ports found", "")
        else:
            for port in ports:
                self.port_combo.addItem(port, port)
            if current in ports:
                self.port_combo.setCurrentIndex(ports.index(current))
        self.port_combo.blockSignals(False)

    # 연결 상태 변화에 따라 버튼 활성화와 상태 문구를 갱신합니다.
    def set_connected(self, connected, port_text):
        self.led.set_connected(connected)
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected)
        self.port_combo.setEnabled(not connected)
        self.refresh_button.setEnabled(not connected)
        if connected:
            self.status_label.setText(f"Arduino Connected: {port_text}")
        else:
            self.status_label.setText(f"Arduino Disconnected: {port_text}")


# 공정 단계를 탭처럼 보여주고, 클릭으로 모드 전환 요청을 보내는 위젯입니다.
class ProcessStepBar(QWidget):
    step_selected = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._labels = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        for state, title in (
            (ProcessState.IDLE, "Idle"),
            (ProcessState.ALIGNING, "Align"),
            (ProcessState.EXPOSING, "Expose"),
            (ProcessState.MOVING, "Move"),
            (ProcessState.INSPECTING, "Inspect"),
            (ProcessState.ET_TEST, "ET-Test"),
            (ProcessState.SORTING, "Sort"),
        ):
            button = QPushButton(title)
            button.setMinimumHeight(44)
            button.clicked.connect(lambda _=False, s=state: self.step_selected.emit(s))
            layout.addWidget(button)
            self._labels[state] = button

        self.update_state(ProcessState.IDLE)

    # 현재 단계만 강조 표시하고 나머지는 비활성 스타일로 바꿉니다.
    def update_state(self, current_state):
        for state, button in self._labels.items():
            if state == current_state:
                button.setStyleSheet(
                    "QPushButton { background-color: #89b4fa; color: #1e1e2e; border-radius: 8px; font-weight: 800; }"
                )
            else:
                button.setStyleSheet(
                    "QPushButton { background-color: #45475a; color: #cdd6f4; border-radius: 8px; font-weight: 700; }"
                )


# 모든 공정에서 공통으로 사용하는 좌측 디버그 로그 패널입니다.
class DebugPanel(QGroupBox):
    def __init__(self):
        super().__init__("Debug Log")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 18, 8, 8)
        layout.setSpacing(6)
        self.setMinimumHeight(180)
        self.setMaximumHeight(240)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(130)
        layout.addWidget(self.log_view)

    # 새 로그를 추가하고 항상 마지막 줄이 보이도록 스크롤합니다.
    def append_log(self, text):
        self.log_view.appendPlainText(text)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())


# 모든 공정에서 같은 위치에 고정되는 공통 안전 제어 패널입니다.
class SafetyPanel(QGroupBox):
    emergency_stop = pyqtSignal()
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    restart_requested = pyqtSignal()

    def __init__(self):
        super().__init__("System Control")
        self.setMinimumWidth(380)
        self.setMinimumHeight(300)
        self._build_ui()

    # 상태 표시, E-Stop, Start/Stop/Restart 버튼을 생성합니다.
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 20, 10, 10)
        layout.setSpacing(10)

        self.status_label = QLabel("System Healthy")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumHeight(118)
        self.status_label.setStyleSheet(
            "QLabel { background-color: #45475a; border: 1px solid #585b70; border-radius: 8px; font-size: 16pt; font-weight: 800; }"
        )
        layout.addWidget(self.status_label)

        self.estop_button = QPushButton("EMERGENCY STOP")
        self.estop_button.setObjectName("btnStop")
        self.estop_button.setMinimumHeight(118)
        self.estop_button.setFont(QFont("Segoe UI", 20, QFont.Weight.Black))
        self.estop_button.clicked.connect(self.emergency_stop.emit)
        layout.addWidget(self.estop_button)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.start_button = QPushButton("Start")
        self.start_button.setObjectName("btnRun")
        self.start_button.setMinimumHeight(54)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("btnWarn")
        self.stop_button.setEnabled(False)
        self.stop_button.setMinimumHeight(54)
        self.restart_button = QPushButton("Restart")
        self.restart_button.setMinimumHeight(54)
        self.start_button.clicked.connect(self.start_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self.restart_button.clicked.connect(self.restart_requested.emit)
        actions.addWidget(self.start_button, 1)
        actions.addWidget(self.stop_button, 1)
        actions.addWidget(self.restart_button, 1)
        layout.addLayout(actions)

    # 시스템 상태 문구와 색상을 통일된 방식으로 갱신합니다.
    def set_status(self, text, critical=False):
        self.status_label.setText(text)
        if critical:
            self.status_label.setStyleSheet(
                "QLabel { background-color: #f38ba8; color: #1e1e2e; border-radius: 8px; font-size: 16pt; font-weight: 900; }"
            )
        else:
            self.status_label.setStyleSheet(
                "QLabel { background-color: #45475a; border: 1px solid #585b70; border-radius: 8px; font-size: 16pt; font-weight: 800; }"
            )


# 속도, 노광 시간 등 자주 바꾸는 값을 조정하는 설정 대화상자입니다.
class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(360, 240)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.align_speed_spin = QDoubleSpinBox()
        self.align_speed_spin.setRange(0.1, 100.0)
        self.align_speed_spin.setValue(self._settings["align_speed"])

        self.jog_speed_spin = QDoubleSpinBox()
        self.jog_speed_spin.setRange(0.1, 100.0)
        self.jog_speed_spin.setValue(self._settings["jog_speed"])

        self.rotation_speed_spin = QDoubleSpinBox()
        self.rotation_speed_spin.setRange(0.1, 100.0)
        self.rotation_speed_spin.setValue(self._settings["rotation_speed"])

        self.exposure_spin = QDoubleSpinBox()
        self.exposure_spin.setRange(0.5, 60.0)
        self.exposure_spin.setValue(self._settings["exposure_time_sec"])

        form.addRow("Align Speed", self.align_speed_spin)
        form.addRow("Linear Jog Speed", self.jog_speed_spin)
        form.addRow("Rotation Jog Speed", self.rotation_speed_spin)
        form.addRow("Exposure Time (s)", self.exposure_spin)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        )
        cancel_button = QPushButton("Cancel")
        apply_button = QPushButton("Apply")
        cancel_button.clicked.connect(self.reject)
        apply_button.clicked.connect(self.accept)
        buttons.addWidget(cancel_button)
        buttons.addWidget(apply_button)
        layout.addLayout(buttons)

    # UI에서 입력한 설정값을 dict 형태로 반환합니다.
    def values(self):
        return {
            "align_speed": self.align_speed_spin.value(),
            "jog_speed": self.jog_speed_spin.value(),
            "rotation_speed": self.rotation_speed_spin.value(),
            "exposure_time_sec": self.exposure_spin.value(),
        }


# 검사 공정의 누적 수율 통계를 표시하는 위젯입니다.
class YieldWidget(QGroupBox):
    def __init__(self):
        super().__init__("Yield")
        self.total_count = 0
        self.pass_count = 0

        layout = QFormLayout(self)
        self.total_label = QLabel("0")
        self.pass_label = QLabel("0")
        self.fail_label = QLabel("0")
        self.yield_label = QLabel("0.0%")
        for widget in (self.total_label, self.pass_label, self.fail_label, self.yield_label):
            widget.setStyleSheet(
                "QLabel { background-color: #45475a; border: 1px solid #585b70; border-radius: 4px; padding: 6px 10px; font-weight: 800; }"
            )
        layout.addRow("Total", self.total_label)
        layout.addRow("Pass", self.pass_label)
        layout.addRow("Fail", self.fail_label)
        layout.addRow("Yield", self.yield_label)

    # 검사 결과 1건을 반영해 총량과 수율을 즉시 갱신합니다.
    def record(self, passed):
        self.total_count += 1
        if passed:
            self.pass_count += 1
        fail_count = self.total_count - self.pass_count
        yield_rate = (self.pass_count / self.total_count) * 100 if self.total_count else 0.0
        self.total_label.setText(str(self.total_count))
        self.pass_label.setText(str(self.pass_count))
        self.fail_label.setText(str(fail_count))
        self.yield_label.setText(f"{yield_rate:.1f}%")


# ET-Test 결과를 웨이퍼 타일 맵 형태로 시각화하는 위젯입니다.
class WaferMapWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(320)
        self._pin_states = []
        self._row_counts = [5, 7, 8, 8, 8, 8, 8, 7, 5]

    @property
    # 현재 웨이퍼를 구성하는 총 타일 개수를 반환합니다.
    def tile_count(self):
        return sum(self._row_counts)

    # 타일별 정상/불량 상태 목록을 받아 화면을 다시 그립니다.
    def set_pin_states(self, states):
        self._pin_states = list(states)
        self.update()

    # 참고 이미지 느낌처럼 사각 타일 배열 형태의 웨이퍼를 그립니다.
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(18, 18, -18, -18)
        row_count = len(self._row_counts)
        max_cols = max(self._row_counts)
        gap = 6
        cell_size = min(
            max(16, int((rect.width() - gap * (max_cols - 1)) / max_cols)),
            max(16, int((rect.height() - gap * (row_count - 1)) / row_count)),
        )
        total_height = row_count * cell_size + (row_count - 1) * gap
        start_y = rect.center().y() - (total_height // 2)
        state_index = 0

        for row_index, cols in enumerate(self._row_counts):
            row_width = cols * cell_size + (cols - 1) * gap
            start_x = rect.center().x() - (row_width // 2)
            y = start_y + row_index * (cell_size + gap)
            for col_index in range(cols):
                x = start_x + col_index * (cell_size + gap)
                state = self._pin_states[state_index] if state_index < len(self._pin_states) else None
                if state is True:
                    fill = QColor("#78c8ff")
                elif state is False:
                    fill = QColor("#ef8567")
                else:
                    fill = QColor("#5a6075")
                painter.setPen(QColor("#89b4fa") if state is not False else QColor("#f2a58c"))
                painter.setBrush(fill)
                painter.drawRoundedRect(x, y, cell_size, cell_size, 3, 3)
                state_index += 1

        painter.end()
