# 비전 검사/판별 공정 전용 UI 모듈입니다.
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget

from ..components import VideoPanel, YieldWidget


# 검사 카메라, 마지막 스냅샷, PASS/FAIL 판정 UI를 담당합니다.
class InspectPageModule(QObject):
    inspection_decided = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._latest_snapshot = None
        self.left_panel = QWidget()
        self.center_panel = QWidget()
        self.right_panel = QWidget()
        self._build_left_panel()
        self._build_center_panel()
        self._build_right_panel()

    # 좌측에는 마지막 검사 스냅샷을 배치합니다.
    def _build_left_panel(self):
        layout = QVBoxLayout(self.left_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        snapshot_group = QGroupBox("Last Result Snapshot")
        snapshot_layout = QVBoxLayout(snapshot_group)
        self.snapshot_panel = VideoPanel("No Snapshot")
        self.snapshot_panel.setMinimumSize(320, 220)
        snapshot_layout.addWidget(self.snapshot_panel)
        layout.addWidget(snapshot_group)
        layout.addStretch(1)

    # 중앙에는 검사 카메라 실시간 화면을 배치합니다.
    def _build_center_panel(self):
        layout = QVBoxLayout(self.center_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        title = QLabel("Inspection / Sorting")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setMinimumHeight(34)
        layout.addWidget(title)
        self.video_panel = VideoPanel("Inspector Camera Feed")
        self.video_panel.setMinimumSize(760, 560)
        layout.addWidget(self.video_panel, 1)

    # 우측에는 AI 판정 결과와 누적 수율 통계를 배치합니다.
    def _build_right_panel(self):
        layout = QVBoxLayout(self.right_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        result_group = QGroupBox("AI Decision")
        result_layout = QVBoxLayout(result_group)
        self.result_label = QLabel("WAIT")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setMinimumHeight(110)
        self.result_label.setStyleSheet(
            "QLabel { background-color: #45475a; border: 1px solid #585b70; border-radius: 6px; font-size: 28px; font-weight: 900; }"
        )
        self.pass_button = QPushButton("PASS")
        self.pass_button.setObjectName("btnConnect")
        self.fail_button = QPushButton("FAIL")
        self.fail_button.setObjectName("btnDisconnect")
        self.pass_button.clicked.connect(lambda: self._set_result(True))
        self.fail_button.clicked.connect(lambda: self._set_result(False))
        result_layout.addWidget(self.result_label)
        result_layout.addWidget(self.pass_button)
        result_layout.addWidget(self.fail_button)
        layout.addWidget(result_group)

        self.yield_widget = YieldWidget()
        layout.addWidget(self.yield_widget)
        layout.addStretch(1)

    # 최신 검사 프레임을 갱신하고 스냅샷 후보로 저장합니다.
    def update_frame(self, image):
        self.video_panel.set_frame(image)
        self._latest_snapshot = image

    # 사용자가 선택한 검사 결과를 UI와 수율 통계에 반영합니다.
    def _set_result(self, passed):
        if self._latest_snapshot is not None:
            self.snapshot_panel.set_frame(self._latest_snapshot)
        if passed:
            self.result_label.setText("PASS")
            self.result_label.setStyleSheet(
                "QLabel { background-color: #a6e3a1; color: #1e1e2e; border-radius: 6px; font-size: 28px; font-weight: 900; }"
            )
        else:
            self.result_label.setText("FAIL")
            self.result_label.setStyleSheet(
                "QLabel { background-color: #f38ba8; color: #1e1e2e; border-radius: 6px; font-size: 28px; font-weight: 900; }"
            )
        self.yield_widget.record(passed)
        self.inspection_decided.emit(passed)
