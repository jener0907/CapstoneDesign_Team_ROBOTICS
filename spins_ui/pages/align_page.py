# 정렬/노광 공정 전용 UI 모듈입니다.
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QProgressBar,
)

from ..components import VideoPanel


# 자동 정렬, 수동 얼라인, 노광 진행 표시를 담당하는 페이지입니다.
class AlignPageModule(QObject):
    linear_home_requested = pyqtSignal()
    manual_align_requested = pyqtSignal()
    jog_pressed = pyqtSignal(str)
    jog_released = pyqtSignal()
    linear_speed_changed = pyqtSignal(float)
    rotation_speed_changed = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.left_panel = QScrollArea()
        self.center_panel = QWidget()
        self.right_panel = QWidget()
        self.jog_buttons = []
        self.jog_button_map = {}
        self._build_left_panel()
        self._build_center_panel()
        self._build_right_panel()

    # 좌측에는 조그와 수동 얼라인 제어만 배치합니다.
    def _build_left_panel(self):
        self.left_panel.setWidgetResizable(True)
        self.left_panel.setFrameShape(QScrollArea.Shape.NoFrame)
        self.left_panel.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        self.left_panel.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        linear_group = QGroupBox("Linear Stage")
        linear_layout = QVBoxLayout(linear_group)
        linear_layout.setContentsMargins(12, 18, 12, 12)
        linear_layout.setSpacing(8)
        self.linear_home_button = QPushButton("Linear Home")
        self.linear_home_button.setObjectName("btnRun")
        self.linear_home_button.setMinimumHeight(40)
        self.linear_home_button.clicked.connect(self.linear_home_requested.emit)
        self.linear_home_status = QLabel("Home required")
        self.linear_home_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.linear_home_status.setMinimumHeight(36)
        self.linear_home_status.setStyleSheet(
            "QLabel { background-color: #45475a; border: 1px solid #585b70; border-radius: 6px; padding: 6px 10px; font-weight: 800; }"
        )
        linear_layout.addWidget(self.linear_home_button)
        linear_layout.addWidget(self.linear_home_status)
        layout.addWidget(linear_group)

        jog_group = QGroupBox("Jog Control")
        jog_layout = QVBoxLayout(jog_group)
        jog_layout.setContentsMargins(12, 18, 12, 12)
        jog_layout.setSpacing(10)

        position_row = QHBoxLayout()
        position_row.setSpacing(12)
        self.x_position_value = QLabel("X 0.00 mm")
        self.y_position_value = QLabel("Y 0.00 mm")
        for widget in (self.x_position_value, self.y_position_value):
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            widget.setMinimumHeight(36)
            widget.setMinimumWidth(0)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            widget.setStyleSheet(
                "QLabel { background-color: #45475a; border: 1px solid #585b70; border-radius: 6px; padding: 6px 10px; font-weight: 800; }"
            )
            position_row.addWidget(widget, 1)
        jog_layout.addLayout(position_row)

        jog_grid = QGridLayout()
        jog_grid.setContentsMargins(0, 0, 0, 0)
        jog_grid.setHorizontalSpacing(10)
        jog_grid.setVerticalSpacing(10)
        jog_grid.setColumnStretch(0, 1)
        jog_grid.setColumnStretch(1, 1)
        jog_grid.setColumnStretch(2, 1)

        buttons = {
            (1, 0): ("X+", "JOG_X_POS"),
            (2, 0): ("X-", "JOG_X_NEG"),
            (1, 1): ("Y+", "JOG_Y_POS"),
            (2, 1): ("Y-", "JOG_Y_NEG"),
            (1, 2): ("R+", "JOG_R_POS"),
            (2, 2): ("R-", "JOG_R_NEG"),
        }
        for (row, col), (text, command) in buttons.items():
            button = QPushButton(text)
            button.setMinimumHeight(40)
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.pressed.connect(lambda cmd=command: self.jog_pressed.emit(cmd))
            button.released.connect(self.jog_released.emit)
            jog_grid.addWidget(button, row, col)
            self.jog_buttons.append(button)
            self.jog_button_map[command] = button
        jog_layout.addLayout(jog_grid)
        layout.addWidget(jog_group)

        speed_group = QGroupBox("Speed Control")
        speed_layout = QVBoxLayout(speed_group)
        speed_layout.setContentsMargins(12, 18, 12, 12)
        speed_layout.setSpacing(6)

        self.linear_speed_spin = QDoubleSpinBox()
        self.linear_speed_spin.setRange(1.0, 100.0)
        self.linear_speed_spin.setSuffix(" %")
        self.linear_speed_spin.setMinimumHeight(30)
        self.linear_speed_spin.valueChanged.connect(self.linear_speed_changed.emit)

        self.rotation_speed_spin = QDoubleSpinBox()
        self.rotation_speed_spin.setRange(1.0, 100.0)
        self.rotation_speed_spin.setSuffix(" %")
        self.rotation_speed_spin.setMinimumHeight(30)
        self.rotation_speed_spin.valueChanged.connect(self.rotation_speed_changed.emit)

        speed_layout.addWidget(self._section_label("XY Jog Speed"))
        speed_layout.addWidget(self.linear_speed_spin)
        speed_layout.addWidget(self._section_label("R Jog Speed"))
        speed_layout.addWidget(self.rotation_speed_spin)

        manual_group = QGroupBox("Manual Align")
        manual_layout = QVBoxLayout(manual_group)
        manual_layout.setContentsMargins(12, 18, 12, 12)
        manual_layout.setSpacing(8)
        self.manual_align_button = QPushButton("Manual Align")
        self.manual_align_button.setObjectName("btnWarn")
        self.manual_align_button.setMinimumHeight(72)
        self.manual_align_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.manual_align_button.clicked.connect(self.manual_align_requested.emit)
        manual_layout.addWidget(self.manual_align_button)

        speed_manual_row = QHBoxLayout()
        speed_manual_row.setSpacing(10)
        speed_manual_row.addWidget(speed_group, 3)
        speed_manual_row.addWidget(manual_group, 2)
        layout.addLayout(speed_manual_row)

    # 중앙에는 실제 얼라인 카메라 화면을 배치합니다.
    def _build_center_panel(self):
        layout = QVBoxLayout(self.center_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        title = QLabel("Align / Expose")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setMinimumHeight(34)
        layout.addWidget(title)
        self.video_panel = VideoPanel("Aligner Camera Feed")
        self.video_panel.setMinimumSize(760, 560)
        layout.addWidget(self.video_panel, 1)

    # 우측에는 비전 결과와 노광 진행 정보를 모아 배치합니다.
    def _build_right_panel(self):
        layout = QVBoxLayout(self.right_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        vision_group = QGroupBox("Vision Result")
        vision_group.setMinimumHeight(228)
        vision_layout = QVBoxLayout(vision_group)
        vision_layout.setSpacing(10)

        self.angle_value = QLabel("--")
        self.angle_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.angle_value.setMinimumHeight(82)
        self.angle_value.setStyleSheet(
            "QLabel { background-color: #45475a; border: 1px solid #585b70; border-radius: 8px; padding: 8px 12px; font-size: 18pt; font-weight: 900; color: #f9e2af; }"
        )
        self.status_value = QLabel("WAITING")
        self.status_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_value.setMinimumHeight(58)

        vision_layout.addWidget(self._section_label("Angle"))
        vision_layout.addWidget(self.angle_value)
        vision_layout.addWidget(self._section_label("Status"))
        vision_layout.addWidget(self.status_value)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(10)
        self.key_value = QLabel("0")
        self.wafer_value = QLabel("0")
        for title, widget in (("Keys", self.key_value), ("Wafer", self.wafer_value)):
            card = QWidget()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(4)
            card_layout.addWidget(self._section_label(title))
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            widget.setMinimumHeight(52)
            widget.setStyleSheet(
                "QLabel { background-color: #45475a; border: 1px solid #585b70; border-radius: 6px; padding: 8px 10px; font-size: 13pt; font-weight: 900; }"
            )
            card_layout.addWidget(widget)
            summary_row.addWidget(card)
        vision_layout.addLayout(summary_row)
        layout.addWidget(vision_group)

        exposure_group = QGroupBox("Exposure")
        exposure_group.setMinimumHeight(188)
        exposure_layout = QVBoxLayout(exposure_group)
        exposure_layout.setContentsMargins(14, 18, 14, 14)
        exposure_layout.setSpacing(10)
        self.expose_button = QPushButton("Auto After Align")
        self.expose_button.setEnabled(False)
        self.expose_button.setMinimumHeight(50)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")
        self.progress_bar.setMinimumHeight(34)
        exposure_layout.addWidget(self.expose_button)
        exposure_layout.addWidget(self.progress_bar)
        layout.addWidget(exposure_group)
        self._apply_status_style("WAITING")

    @staticmethod
    # 카드형 정보 위젯의 공통 제목 라벨 생성 함수입니다.
    def _section_label(text):
        label = QLabel(text)
        label.setStyleSheet("QLabel { color: #a6adc8; font-size: 10pt; font-weight: 700; }")
        return label

    # 얼라인 상태에 따라 상태 카드 색을 바꿉니다.
    def _apply_status_style(self, status_text):
        if status_text == "ALIGNED":
            style = "QLabel { background-color: #a6e3a1; color: #1e1e2e; border-radius: 8px; padding: 8px 12px; font-size: 11pt; font-weight: 900; }"
        elif status_text == "UPSIDE DOWN":
            style = "QLabel { background-color: #f38ba8; color: #1e1e2e; border-radius: 8px; padding: 8px 12px; font-size: 11pt; font-weight: 900; }"
        else:
            style = "QLabel { background-color: #89b4fa; color: #1e1e2e; border-radius: 8px; padding: 8px 12px; font-size: 11pt; font-weight: 900; }"
        self.status_value.setStyleSheet(style)

    # 메인 윈도우에서 받은 최신 얼라인 영상을 반영합니다.
    def update_frame(self, image):
        self.video_panel.set_frame(image)

    # 비전 추론 결과를 우측 정보 패널에 반영합니다.
    def update_metadata(self, metadata):
        angle = metadata.get("angle_deg")
        self.angle_value.setText(f"{angle:.2f} deg" if angle is not None else "--")
        status_text = metadata.get("status_text", "WAITING")
        self.status_value.setText(status_text)
        self._apply_status_style(status_text)
        self.key_value.setText(str(metadata.get("key_count", 0)))
        self.wafer_value.setText(str(metadata.get("wafer_count", 0)))

    # 노광 진행률과 상태 문구를 갱신합니다.
    def set_exposure_value(self, value, label):
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(label)

    # 리니어 스테이지 호밍 완료 여부를 좌측 패널에 반영합니다.
    def set_linear_stage_ready(self, ready, message=None):
        if ready:
            text = message or "Linear stage homed"
            style = "QLabel { background-color: #a6e3a1; color: #1e1e2e; border: 1px solid #585b70; border-radius: 6px; padding: 6px 10px; font-weight: 800; }"
        else:
            text = message or "Home required"
            style = "QLabel { background-color: #fab387; color: #1e1e2e; border: 1px solid #585b70; border-radius: 6px; padding: 6px 10px; font-weight: 800; }"
        self.linear_home_status.setText(text)
        self.linear_home_status.setStyleSheet(style)

    # 축별 사용 여부에 따라 조그 버튼 표시 상태를 쉽게 조정합니다.
    def set_axis_enabled(self, command, enabled):
        button = self.jog_button_map.get(command)
        if button is not None:
            button.setEnabled(enabled)

    # X/Y 현재 추정 위치를 mm 단위로 갱신합니다.
    def update_stage_position(self, x_mm, y_mm):
        self.x_position_value.setText(f"X {x_mm:.2f} mm")
        self.y_position_value.setText(f"Y {y_mm:.2f} mm")

    # 메인 설정값을 좌측 속도 조절 UI에 반영합니다.
    def set_speed_values(self, linear_speed, rotation_speed):
        self.linear_speed_spin.blockSignals(True)
        self.rotation_speed_spin.blockSignals(True)
        self.linear_speed_spin.setValue(linear_speed)
        self.rotation_speed_spin.setValue(rotation_speed)
        self.linear_speed_spin.blockSignals(False)
        self.rotation_speed_spin.blockSignals(False)
