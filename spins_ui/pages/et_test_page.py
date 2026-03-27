# EDS ET-Test 공정 전용 UI 모듈입니다.
import random

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFormLayout, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget

from ..components import VideoPanel, WaferMapWidget


# ET-Test 카메라, 실행 버튼, 웨이퍼 맵, 핀 수율 요약을 담당합니다.
class ETTestPageModule(QObject):
    complete_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.left_panel = QWidget()
        self.center_panel = QWidget()
        self.right_panel = QWidget()
        self._build_left_panel()
        self._build_center_panel()
        self._build_right_panel()

    # 좌측에는 테스트 실행 버튼과 범례를 배치합니다.
    def _build_left_panel(self):
        layout = QVBoxLayout(self.left_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        control_group = QGroupBox("ET-Test Control")
        control_layout = QVBoxLayout(control_group)
        self.run_button = QPushButton("Run ET-Test")
        self.run_button.setObjectName("btnRun")
        self.complete_button = QPushButton("Complete ET-Test")
        self.complete_button.setObjectName("btnConnect")
        self.clear_button = QPushButton("Clear Map")
        control_layout.addWidget(self.run_button)
        control_layout.addWidget(self.complete_button)
        control_layout.addWidget(self.clear_button)
        layout.addWidget(control_group)

        legend_group = QGroupBox("Legend")
        legend_layout = QVBoxLayout(legend_group)
        legend_layout.addWidget(QLabel("Light Blue: PASS"))
        legend_layout.addWidget(QLabel("Light Red: FAIL"))
        legend_layout.addWidget(QLabel("Gray: Untested"))
        layout.addWidget(legend_group)
        layout.addStretch(1)

    # 중앙에는 ET-Test 카메라 화면을 배치합니다.
    def _build_center_panel(self):
        layout = QVBoxLayout(self.center_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        title = QLabel("EDS / ET-Test")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setMinimumHeight(34)
        layout.addWidget(title)
        self.video_panel = VideoPanel("ET-Test Camera Feed")
        self.video_panel.setMinimumSize(760, 560)
        layout.addWidget(self.video_panel, 1)

    # 우측에는 핀 수율 요약과 웨이퍼 타일 맵을 배치합니다.
    def _build_right_panel(self):
        layout = QVBoxLayout(self.right_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        summary_group = QGroupBox("Yield Summary")
        summary_layout = QFormLayout(summary_group)
        self.total_label = QLabel("0")
        self.pass_label = QLabel("0")
        self.fail_label = QLabel("0")
        self.yield_label = QLabel("0.0%")
        for label in (self.total_label, self.pass_label, self.fail_label, self.yield_label):
            label.setStyleSheet(
                "QLabel { background-color: #45475a; border: 1px solid #585b70; border-radius: 6px; padding: 6px 10px; font-weight: 800; }"
            )
        summary_layout.addRow("Pins Tested", self.total_label)
        summary_layout.addRow("Pass Pins", self.pass_label)
        summary_layout.addRow("Fail Pins", self.fail_label)
        summary_layout.addRow("Pin Yield", self.yield_label)
        layout.addWidget(summary_group)

        wafer_group = QGroupBox("Wafer Contact Map")
        wafer_layout = QVBoxLayout(wafer_group)
        self.wafer_map = WaferMapWidget()
        wafer_layout.addWidget(self.wafer_map)
        layout.addWidget(wafer_group, 1)
        self.complete_button.clicked.connect(self.complete_requested.emit)

    # 최신 ET-Test 카메라 영상을 갱신합니다.
    def update_frame(self, image):
        self.video_panel.set_frame(image)

    # 현재 웨이퍼 맵과 수율 통계를 초기화합니다.
    def clear_map(self):
        self.wafer_map.set_pin_states([])
        self.total_label.setText("0")
        self.pass_label.setText("0")
        self.fail_label.setText("0")
        self.yield_label.setText("0.0%")

    # 현재는 시뮬레이션 방식으로 ET-Test 결과를 생성해 맵에 반영합니다.
    def run_test(self, inspection_passed=True):
        pin_count = self.wafer_map.tile_count
        fail_probability = 0.08 if inspection_passed else 0.22
        states = [random.random() > fail_probability for _ in range(pin_count)]
        pass_count = sum(1 for state in states if state)
        fail_count = pin_count - pass_count
        yield_rate = (pass_count / pin_count) * 100 if pin_count else 0.0

        self.wafer_map.set_pin_states(states)
        self.total_label.setText(str(pin_count))
        self.pass_label.setText(str(pass_count))
        self.fail_label.setText(str(fail_count))
        self.yield_label.setText(f"{yield_rate:.1f}%")
