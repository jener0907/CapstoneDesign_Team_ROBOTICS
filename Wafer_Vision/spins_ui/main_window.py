# 통합 HMI의 메인 윈도우입니다.
# 공정 상태 전환, 카메라/시리얼 관리, 공통 안전 제어를 여기서 묶습니다.
import cv2
import sys

from PyQt6.QtCore import QSettings, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .components import DebugPanel, ProcessStepBar, SafetyPanel, SerialBar, SettingsDialog
from .config import (
    ALIGNER_CAMERA_INDEX,
    ALIGNER_MODEL_PATH,
    AUTO_ALIGN_CREEP_SETTLE_MS,
    AUTO_ALIGN_CREEP_THRESHOLD_DEG,
    AUTO_ALIGN_POLL_MS,
    AUTO_ALIGN_RELEASE_DEG,
    AUTO_ALIGN_SLOWDOWN_DEG,
    AUTO_ALIGN_STABLE_FRAMES,
    AUTO_ALIGN_TARGET_DEG,
    AUTO_ALIGN_X_FINE_PX,
    AUTO_ALIGN_X_RELEASE_PX,
    AUTO_ALIGN_X_STABLE_FRAMES,
    AUTO_ALIGN_X_TARGET_PX,
    AUTO_ALIGN_ZERO_LOCK_DEG,
    DEFAULT_BAUDRATE,
    ENABLE_R_STAGE,
    ENABLE_X_STAGE,
    ENABLE_Y_STAGE,
    INSPECTOR_CAMERA_INDEX,
    LINEAR_TRAVEL_MM,
    MANUAL_JOG_HOLD_MS,
    REQUIRE_LINEAR_HOME_FOR_PROCESS,
    R_JOG_TAP_DEG,
    SKIP_X_HOME,
    SKIP_Y_HOME,
    linear_steps_per_mm,
    linear_steps_to_mm,
)
from .core import CameraThread, ProcessState, SerialManager, StateManager, frame_to_qimage
from .pages.align_page import AlignPageModule
from .pages.et_test_page import ETTestPageModule
from .pages.inspect_page import InspectPageModule
from .styles import DARK_STYLESHEET

CAM_OVERLAY_X1 = 18
CAM_OVERLAY_Y1 = 18
CAM_OVERLAY_X2 = 130
CAM_OVERLAY_Y2 = 54
CAM_OVERLAY_TEXT_X = 30
CAM_OVERLAY_TEXT_Y = 42
CAM_OVERLAY_FILL_COLOR = (49, 50, 68)
CAM_OVERLAY_BORDER_COLOR = (88, 91, 112)
CAM_OVERLAY_TEXT_COLOR = (166, 227, 161)


# 분리된 공정 모듈을 하나로 묶는 최상위 윈도우입니다.
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SPINS Integrated HMI (Qt6)")
        self.setMinimumSize(1680, 980)
        self.settings_store = QSettings("SPINS", "IntegratedHMI")

        self.state_manager = StateManager()
        self.serial_manager = SerialManager()
        self.aligner_thread = None
        self.inspector_thread = None

        self.current_alignment_error = 0.0
        self.current_alignment_stop_error = 0.0
        self.current_x_alignment_error_px = 0.0
        self.current_is_upside_down = False
        self.emergency_stop_active = False
        self.linear_stage_homed = False
        self.linear_homing_active = False
        self.x_position_steps = 0
        self.y_position_steps = 0
        self.process_running = False
        self.is_auto_aligning = False
        self.is_motor_busy = False
        self.auto_align_stable_count = 0
        self.auto_align_x_stable_count = 0
        self.auto_align_phase = "x"
        self.align_sequence_source = "Auto"
        self.x_align_continuous_active = False
        self.x_align_active_command = None
        self.x_align_active_speed = 0.0
        self.r_align_continuous_active = False
        self.r_align_active_command = None
        self.r_align_active_speed = 0.0
        self.r_zero_crossed = False
        self.r_last_stop_error_sign = 0
        self.last_active_state = ProcessState.ALIGNING
        self.pending_jog_command = None
        self.continuous_jog_active = False
        self.last_inspection_result = True

        self.settings = {
            "align_speed": 6.0,
            "jog_speed": 75.0,
            "rotation_speed": 60.0,
            "exposure_time_sec": 2.0,
        }

        self.auto_align_timer = QTimer(self)
        self.auto_align_timer.timeout.connect(self._auto_align_loop)

        self.serial_poll_timer = QTimer(self)
        self.serial_poll_timer.timeout.connect(self._poll_serial_responses)

        self.exposure_timer = QTimer(self)
        self.exposure_timer.timeout.connect(self._advance_exposure)
        self.exposure_progress = 0

        self.jog_hold_timer = QTimer(self)
        self.jog_hold_timer.setSingleShot(True)
        self.jog_hold_timer.timeout.connect(self._begin_continuous_jog)

        self._control_widgets = []

        self._build_ui()
        self._connect_signals()
        self.align_module.update_stage_position(0.0, 0.0)
        self.align_module.set_speed_values(self.settings["jog_speed"], self.settings["rotation_speed"])
        self._refresh_ports()
        self._start_camera_threads()
        self.serial_poll_timer.start(50)
        self.state_manager.set_state(ProcessState.ALIGNING)
        self._update_run_controls()
        self._update_status_bar()

    # 상단 바, 좌/중/우 스택, 공통 안전 패널을 조립합니다.
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self.serial_bar = SerialBar()
        root.addWidget(self.serial_bar)

        self.step_bar = ProcessStepBar()
        root.addWidget(self.step_bar)

        self.align_module = AlignPageModule()
        self.inspect_module = InspectPageModule()
        self.et_test_module = ETTestPageModule()

        self.body_splitter = QSplitter()
        self.body_splitter.setChildrenCollapsible(False)
        root.addWidget(self.body_splitter, 1)

        left_column = QWidget()
        left_column.setMinimumWidth(360)
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        self.left_stack = QStackedWidget()
        self.left_stack.addWidget(self.align_module.left_panel)
        self.left_stack.addWidget(self.inspect_module.left_panel)
        self.left_stack.addWidget(self.et_test_module.left_panel)
        self.debug_panel = DebugPanel()
        left_layout.addWidget(self.left_stack, 1)
        left_layout.addWidget(self.debug_panel, 0)
        self.body_splitter.addWidget(left_column)

        self.center_stack = QStackedWidget()
        self.center_stack.addWidget(self.align_module.center_panel)
        self.center_stack.addWidget(self.inspect_module.center_panel)
        self.center_stack.addWidget(self.et_test_module.center_panel)
        self.center_stack.setMinimumWidth(720)
        self.body_splitter.addWidget(self.center_stack)

        right_column = QWidget()
        right_column.setMinimumWidth(420)
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        self.right_stack = QStackedWidget()
        self.right_stack.addWidget(self.align_module.right_panel)
        self.right_stack.addWidget(self.inspect_module.right_panel)
        self.right_stack.addWidget(self.et_test_module.right_panel)
        self.safety_panel = SafetyPanel()
        right_layout.addWidget(self.right_stack, 1)
        right_layout.addWidget(self.safety_panel, 0)
        self.body_splitter.addWidget(right_column)
        self.body_splitter.setStretchFactor(0, 2)
        self.body_splitter.setStretchFactor(1, 4)
        self.body_splitter.setStretchFactor(2, 3)
        self._restore_splitter_state()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self._control_widgets.extend(
            [
                self.serial_bar.connect_button,
                self.serial_bar.disconnect_button,
                self.serial_bar.refresh_button,
                self.serial_bar.port_combo,
                self.serial_bar.settings_button,
                self.align_module.linear_home_button,
                self.align_module.manual_align_button,
                *self.align_module.jog_buttons,
                self.inspect_module.pass_button,
                self.inspect_module.fail_button,
                self.et_test_module.run_button,
                self.et_test_module.complete_button,
                self.et_test_module.clear_button,
            ]
        )

    # 좌/중/우 메인 스플리터 비율을 이전 실행값으로 복원합니다.
    def _restore_splitter_state(self):
        saved_state = self.settings_store.value("main_body_splitter")
        if saved_state and self.body_splitter.restoreState(saved_state):
            return
        self.body_splitter.setSizes([420, 860, 500])

    # 사용자가 끌어 조절한 메인 스플리터 비율을 다음 실행을 위해 저장합니다.
    def _save_splitter_state(self):
        self.settings_store.setValue("main_body_splitter", self.body_splitter.saveState())

    # 시리얼, 공정 모듈, 안전 패널의 시그널을 메인 로직에 연결합니다.
    def _connect_signals(self):
        self.state_manager.state_changed.connect(self._on_state_changed)
        self.serial_manager.connection_changed.connect(self._on_connection_changed)
        self.serial_manager.log_signal.connect(self.debug_panel.append_log)

        self.serial_bar.refresh_requested.connect(self._refresh_ports)
        self.serial_bar.connect_requested.connect(self.serial_manager.connect_port)
        self.serial_bar.disconnect_requested.connect(self.serial_manager.disconnect_port)
        self.serial_bar.settings_requested.connect(self._open_settings)
        self.step_bar.step_selected.connect(self._jump_to_state)

        self.align_module.manual_align_requested.connect(self._manual_align)
        self.align_module.linear_home_requested.connect(self._request_linear_home)
        self.align_module.jog_pressed.connect(self._start_manual_jog)
        self.align_module.jog_released.connect(self._stop_manual_jog)
        self.align_module.linear_speed_changed.connect(self._update_linear_jog_speed)
        self.align_module.rotation_speed_changed.connect(self._update_rotation_jog_speed)

        self.inspect_module.inspection_decided.connect(self._on_inspection_complete)

        self.et_test_module.run_button.clicked.connect(self._run_et_test_manually)
        self.et_test_module.complete_requested.connect(self._complete_et_test)
        self.et_test_module.clear_button.clicked.connect(self.et_test_module.clear_map)

        self.safety_panel.emergency_stop.connect(self._on_emergency_stop)
        self.safety_panel.start_requested.connect(self._start_or_resume_process)
        self.safety_panel.stop_requested.connect(self._stop_process)
        self.safety_panel.restart_requested.connect(self._restart_process)

    # 현재 사용 가능한 포트를 다시 스캔합니다.
    def _refresh_ports(self):
        ports = self.serial_manager.available_ports()
        self.serial_bar.set_ports(ports)
        self.debug_panel.append_log(f"[Serial] Detected ports: {ports if ports else 'none'}")

    # 설정 대화상자를 열고 변경값을 메인 설정에 반영합니다.
    def _open_settings(self):
        if self.emergency_stop_active:
            return
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings.update(dialog.values())
            self.align_module.set_speed_values(self.settings["jog_speed"], self.settings["rotation_speed"])
            self.debug_panel.append_log(
                f"[Settings] align={self.settings['align_speed']:.1f}, jog={self.settings['jog_speed']:.1f}, rot={self.settings['rotation_speed']:.1f}"
            )

    # 얼라인 화면의 XY 속도 입력을 메인 설정과 즉시 동기화합니다.
    def _update_linear_jog_speed(self, value):
        self.settings["jog_speed"] = float(value)
        self.debug_panel.append_log(f"[Settings] XY jog speed -> {value:.1f}")

    # 얼라인 화면의 R 속도 입력을 메인 설정과 즉시 동기화합니다.
    def _update_rotation_jog_speed(self, value):
        self.settings["rotation_speed"] = float(value)
        self.debug_panel.append_log(f"[Settings] R jog speed -> {value:.1f}")

    # 시리얼 연결 변화에 따라 인터락과 상태 표시를 갱신합니다.
    def _on_connection_changed(self, connected, label):
        self.serial_bar.set_connected(connected, label)
        self.linear_stage_homed = False
        self.linear_homing_active = False
        self.emergency_stop_active = False
        self.x_position_steps = 0
        self.y_position_steps = 0
        self._update_stage_position_display()
        if self._has_required_linear_home_axis():
            self.align_module.set_linear_stage_ready(False, "Home required")
        else:
            self.align_module.set_linear_stage_ready(True, "Linear bypass mode")
        if not connected:
            self._stop_all_motion("Arduino disconnected", critical=True)
            self.align_module.set_exposure_value(0, "Connect Arduino")
        else:
            self.serial_manager.send_command("RESET_ESTOP")
            if self._has_required_linear_home_axis() and REQUIRE_LINEAR_HOME_FOR_PROCESS:
                self.safety_panel.set_status("Run Linear Home first", critical=False)
            else:
                self.safety_panel.set_status("System Healthy", critical=False)
        self._update_run_controls()
        self._update_status_bar()

    # 장비 명령 전송 전에 시리얼 연결 여부를 확인합니다.
    def _ensure_serial_connected(self, action_name):
        if self.serial_manager.is_connected:
            return True
        self.debug_panel.append_log(f"[Serial] {action_name} blocked. Connect Arduino first.")
        self.safety_panel.set_status("Connect Arduino first", critical=True)
        return False

    # 리니어 스테이지 호밍이 끝나지 않았으면 공정 관련 동작을 차단합니다.
    def _ensure_linear_ready(self, action_name):
        if not self._has_required_linear_home_axis():
            return True
        if self.linear_stage_homed:
            return True
        self.debug_panel.append_log(f"[Linear] {action_name} blocked. Run Linear Home first.")
        self.safety_panel.set_status("Run Linear Home first", critical=True)
        self.align_module.set_linear_stage_ready(False, "Home required")
        return False

    # 현재 설정상 X/Y 리니어 축을 실제 사용할지 여부를 반환합니다.
    def _has_enabled_linear_stage(self):
        return ENABLE_X_STAGE or ENABLE_Y_STAGE

    # 실제 홈 대상 축이 하나라도 있는지 판단합니다.
    def _has_required_linear_home_axis(self):
        return (ENABLE_X_STAGE and not SKIP_X_HOME) or (ENABLE_Y_STAGE and not SKIP_Y_HOME)

    # 조그 명령별로 사용 가능한 축인지와 홈 필요 여부를 함께 판단합니다.
    def _can_use_jog_command(self, command):
        if command in {"JOG_R_POS", "JOG_R_NEG"}:
            if ENABLE_R_STAGE:
                return True
            self.debug_panel.append_log("[Jog] R axis is disabled in config.")
            self.safety_panel.set_status("R axis disabled", critical=True)
            return False

        if command in {"JOG_X_POS", "JOG_X_NEG"}:
            if not ENABLE_X_STAGE:
                self.debug_panel.append_log("[Jog] X axis is disabled in config.")
                self.safety_panel.set_status("X axis disabled", critical=True)
                return False
            return True

        if command in {"JOG_Y_POS", "JOG_Y_NEG"}:
            if not ENABLE_Y_STAGE:
                self.debug_panel.append_log("[Jog] Y axis is disabled in config.")
                self.safety_panel.set_status("Y axis disabled", critical=True)
                return False
            return True

        return False

    # 수동 조작을 시작할 때는 UI 내부 E-Stop 상태를 풀어 조그/홈이 바로 먹도록 합니다.
    def _release_emergency_for_manual_control(self, action_name):
        if self.serial_manager.is_connected:
            self.serial_manager.send_command("RESET_ESTOP")
        if not self.emergency_stop_active:
            return True
        self.emergency_stop_active = False
        self.debug_panel.append_log(f"[Safety] Emergency stop cleared for {action_name}.")
        self.safety_panel.set_status("Manual control enabled", critical=False)
        self._set_controls_enabled(True)
        self._update_run_controls()
        return True

    # 내부적으로 추적하는 X/Y 스텝 위치를 mm 카드에 반영합니다.
    def _update_stage_position_display(self):
        x_mm = max(0.0, min(LINEAR_TRAVEL_MM, linear_steps_to_mm(self.x_position_steps)))
        y_mm = max(0.0, min(LINEAR_TRAVEL_MM, linear_steps_to_mm(self.y_position_steps)))
        self.align_module.update_stage_position(x_mm, y_mm)

    # 얼라인/검사 카메라 스레드를 시작합니다.
    def _start_camera_threads(self):
        self.aligner_thread = CameraThread(
            "Aligner",
            ALIGNER_CAMERA_INDEX,
            model_path=ALIGNER_MODEL_PATH,
        )
        self.aligner_thread.frame_ready.connect(self._update_camera_view)
        self.aligner_thread.camera_error.connect(self._camera_error)
        self.aligner_thread.start()

        if INSPECTOR_CAMERA_INDEX == ALIGNER_CAMERA_INDEX:
            self.inspector_thread = None
            self.debug_panel.append_log(
                f"[System] Shared camera mode enabled. Aligner/Inspector both use index {ALIGNER_CAMERA_INDEX}."
            )
        else:
            self.inspector_thread = CameraThread("Inspector", INSPECTOR_CAMERA_INDEX)
            self.inspector_thread.frame_ready.connect(self._update_camera_view)
            self.inspector_thread.camera_error.connect(self._camera_error)
            self.inspector_thread.start()

        self.debug_panel.append_log(
            f"[System] Camera config -> aligner={ALIGNER_CAMERA_INDEX}, inspector={INSPECTOR_CAMERA_INDEX}"
        )
        self.debug_panel.append_log(f"[System] Aligner model -> {ALIGNER_MODEL_PATH}")

    # 카메라 관련 상태 메시지를 사용자에게 보여줍니다.
    def _camera_error(self, message):
        if message == "camera_not found":
            self.debug_panel.append_log("[Camera] camera_not found")
            self.safety_panel.set_status("camera_not found", critical=True)
            return
        self.debug_panel.append_log(message)
        self.safety_panel.set_status(message, critical=True)

    # 시리얼 응답을 주기적으로 읽어 UI 상태와 인터락을 동기화합니다.
    def _poll_serial_responses(self):
        while True:
            response = self.serial_manager.read_line()
            if not response:
                break
            self.debug_panel.append_log(f"[Arduino] {response}")
            self._handle_serial_response(response)

    # 아두이노 문자열 응답을 해석해 호밍/정지/리밋 상태를 반영합니다.
    def _handle_serial_response(self, response):
        if response.startswith("POS:"):
            parts = response.split(":")
            if len(parts) == 5 and parts[1] == "X" and parts[3] == "Y":
                try:
                    self.x_position_steps = int(parts[2])
                    self.y_position_steps = int(parts[4])
                    self._update_stage_position_display()
                except ValueError:
                    pass
            return

        if response == "LINEAR_HOME_STARTED":
            self.linear_homing_active = True
            self.linear_stage_homed = False
            self.align_module.set_linear_stage_ready(False, "Linear homing...")
            self.safety_panel.set_status("Linear homing...", critical=False)
            self._update_run_controls()
            return

        if response == "LINEAR_HOME_DONE":
            self.linear_homing_active = False
            self.linear_stage_homed = True
            self.x_position_steps = 0
            self.y_position_steps = 0
            self._update_stage_position_display()
            self.align_module.set_linear_stage_ready(True, "Linear stage homed")
            self.safety_panel.set_status("System Healthy", critical=False)
            self._update_run_controls()
            return

        if response == "EMERGENCY_STOPPED":
            self.emergency_stop_active = True
            self._stop_all_motion("Emergency stop active", critical=True)
            self.align_module.set_exposure_value(0, "E-Stop Active")
            self._update_run_controls()
            return

        if response == "ESTOP_RESET":
            self.emergency_stop_active = False
            self.linear_homing_active = False
            self.is_motor_busy = False
            if self._has_required_linear_home_axis() and REQUIRE_LINEAR_HOME_FOR_PROCESS and not self.linear_stage_homed:
                self.safety_panel.set_status("Run Linear Home first", critical=False)
            else:
                self.safety_panel.set_status("System Healthy", critical=False)
            self._update_run_controls()
            return

        if response in {"DONE", "JOG_STOPPED", "ABORTED"}:
            self.is_motor_busy = False
            if response == "JOG_STOPPED":
                self.x_align_continuous_active = False
                self.x_align_active_command = None
                self.x_align_active_speed = 0.0
                self.r_align_continuous_active = False
                self.r_align_active_command = None
                self.r_align_active_speed = 0.0
            if response == "ABORTED":
                self._stop_all_motion("Motion aborted", critical=True)
            return

        if response == "ERROR:HOME_REQUIRED":
            self.linear_homing_active = False
            self.linear_stage_homed = False
            self.align_module.set_linear_stage_ready(False, "Home required")
            self.safety_panel.set_status("Run Linear Home first", critical=True)
            self._update_run_controls()
            return

        if response == "ERROR:LINEAR_HOME_FAILED":
            self.linear_homing_active = False
            self.linear_stage_homed = False
            self.align_module.set_linear_stage_ready(False, "Home failed")
            self.safety_panel.set_status("Linear home failed", critical=True)
            self._update_run_controls()
            return

        if response in {"SOFT_LIMIT_X", "SOFT_LIMIT_Y"}:
            self.is_motor_busy = False
            self.safety_panel.set_status(response.replace("_", " "), critical=True)
            return

        if response == "ERROR:ESTOP_ACTIVE":
            self.emergency_stop_active = True
            self.is_motor_busy = False
            self.safety_panel.set_status("Emergency stop active on controller", critical=True)
            self._update_run_controls()
            return

        if response == "ERROR:HOME_REQUIRED":
            self.linear_homing_active = False
            self.linear_stage_homed = False
            self.align_module.set_linear_stage_ready(False, "Home required")
            self.safety_panel.set_status("Run Linear Home first", critical=True)
            self._update_run_controls()
            return

        if response in {"ERROR:X_DISABLED", "ERROR:Y_DISABLED", "ERROR:R_DISABLED"}:
            self.is_motor_busy = False
            axis_name = response.split(":")[-1].replace("_DISABLED", "")
            self.safety_panel.set_status(f"{axis_name} axis disabled in firmware", critical=True)
            self._update_run_controls()
            return

    # 리니어 스테이지 원점 복귀를 요청하고, 완료 전까지 다른 공정을 막습니다.
    def _request_linear_home(self):
        if not self._ensure_serial_connected("Linear Home"):
            return
        self._release_emergency_for_manual_control("Linear Home")
        if not self._has_required_linear_home_axis():
            self.linear_stage_homed = True
            self.linear_homing_active = False
            self.align_module.set_linear_stage_ready(True, "Linear bypass mode")
            self.safety_panel.set_status("System Healthy", critical=False)
            self.debug_panel.append_log("[Linear] No required home axis. Linear home skipped.")
            self._update_run_controls()
            return
        self._stop_jog_immediately()
        self.process_running = False
        self.is_auto_aligning = False
        self.is_motor_busy = False
        self.linear_homing_active = True
        self.linear_stage_homed = False
        self.align_module.set_linear_stage_ready(False, "Linear homing...")
        self.safety_panel.set_status("Linear homing...", critical=False)
        self.serial_manager.send_command(f"HOME_LINEAR:{1 if SKIP_X_HOME else 0}:{1 if SKIP_Y_HOME else 0}")
        self._update_run_controls()

    # 카메라 스레드에서 받은 프레임을 각 공정 화면에 분배합니다.
    def _update_camera_view(self, role, frame, metadata):
        if role == "Aligner":
            self.current_alignment_error = metadata.get("error_to_send", 0.0) or 0.0
            self.current_alignment_stop_error = metadata.get("error_to_stop", self.current_alignment_error) or 0.0
            self.current_x_alignment_error_px = metadata.get("wafer_center_error_px", 0.0) or 0.0
            self.current_is_upside_down = bool(metadata.get("is_upside_down", False))
            align_image = frame_to_qimage(self._draw_aligner_overlay(frame.copy()))
            self.align_module.update_frame(align_image)
            self.align_module.update_metadata(metadata)
            if INSPECTOR_CAMERA_INDEX == ALIGNER_CAMERA_INDEX:
                inspect_image = frame_to_qimage(self._draw_inspector_overlay(frame.copy()))
                self.inspect_module.update_frame(inspect_image)
                self.et_test_module.update_frame(inspect_image)
        elif role == "Inspector":
            inspect_image = frame_to_qimage(self._draw_inspector_overlay(frame.copy()))
            self.inspect_module.update_frame(inspect_image)
            self.et_test_module.update_frame(inspect_image)
        self._update_status_bar()

    # 얼라인 카메라 화면 위에 기준 레티클과 카메라 인덱스를 그립니다.
    def _draw_aligner_overlay(self, frame):
        actual_index = self.aligner_thread.camera_index if self.aligner_thread else ALIGNER_CAMERA_INDEX
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        cv2.line(frame, (cx, 40), (cx, h - 40), (137, 180, 250), 1, cv2.LINE_AA)
        cv2.line(frame, (cx - 40, cy), (cx + 40, cy), (137, 180, 250), 1, cv2.LINE_AA)
        self._draw_camera_overlay(frame, actual_index)
        return frame

    # 검사/ET-Test 카메라 화면 위에 기본 오버레이를 그립니다.
    def _draw_inspector_overlay(self, frame):
        if self.inspector_thread:
            actual_index = self.inspector_thread.camera_index
        elif self.aligner_thread:
            actual_index = self.aligner_thread.camera_index
        else:
            actual_index = INSPECTOR_CAMERA_INDEX
        self._draw_camera_overlay(frame, actual_index)
        return frame

    # 모든 카메라 화면에서 공통으로 쓰는 좌상단 카메라 인덱스 오버레이입니다.
    # 길이, 색, 위치를 한 곳에서만 관리해 페이지별 표시 차이를 막습니다.
    def _draw_camera_overlay(self, frame, camera_index):
        cv2.rectangle(
            frame,
            (CAM_OVERLAY_X1, CAM_OVERLAY_Y1),
            (CAM_OVERLAY_X2, CAM_OVERLAY_Y2),
            CAM_OVERLAY_FILL_COLOR,
            -1,
        )
        cv2.rectangle(
            frame,
            (CAM_OVERLAY_X1, CAM_OVERLAY_Y1),
            (CAM_OVERLAY_X2, CAM_OVERLAY_Y2),
            CAM_OVERLAY_BORDER_COLOR,
            1,
        )
        cv2.putText(
            frame,
            f"CAM {camera_index}",
            (CAM_OVERLAY_TEXT_X, CAM_OVERLAY_TEXT_Y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            CAM_OVERLAY_TEXT_COLOR,
            2,
            cv2.LINE_AA,
        )

    # 상단 단계 바 클릭으로 모드 전환을 요청할 때 호출됩니다.
    def _jump_to_state(self, state):
        if self.process_running or self.is_auto_aligning:
            self.debug_panel.append_log("[UI] Cannot change mode while the cycle is running.")
            return
        self.state_manager.set_state(state)

    # 현재 상태에 맞는 좌/중/우 패널 조합으로 화면을 전환합니다.
    def _switch_page(self, state):
        if state in {ProcessState.IDLE, ProcessState.ALIGNING, ProcessState.EXPOSING, ProcessState.MOVING}:
            index = 0
        elif state == ProcessState.INSPECTING:
            index = 1
        else:
            index = 2
        self.left_stack.setCurrentIndex(index)
        self.center_stack.setCurrentIndex(index)
        self.right_stack.setCurrentIndex(index)

    # 공정 시작 또는 E-Stop 이후 Resume을 담당합니다.
    def _start_or_resume_process(self):
        if self.emergency_stop_active:
            self.emergency_stop_active = False
            if self.serial_manager.is_connected:
                self.serial_manager.send_command("RESET_ESTOP")
            self.debug_panel.append_log("[Safety] Resume requested.")
            self._set_controls_enabled(True)
            if not self.serial_manager.is_connected:
                self.safety_panel.set_status("E-Stop cleared. Connect Arduino first", critical=True)
                self._update_run_controls()
                return
            self.safety_panel.set_status("System Healthy", critical=False)

        if not self._ensure_serial_connected("Start"):
            return
        if REQUIRE_LINEAR_HOME_FOR_PROCESS and not self._ensure_linear_ready("Start"):
            return

        self.process_running = True
        self._update_run_controls()
        if self.state_manager.current_state in {ProcessState.IDLE, ProcessState.ALIGNING}:
            self._start_auto_align()

    # 공정을 처음 정렬 단계부터 다시 시작합니다.
    def _restart_process(self):
        self.emergency_stop_active = False
        if self.serial_manager.is_connected:
            self.serial_manager.send_command("RESET_ESTOP")
        self._set_controls_enabled(True)
        self.debug_panel.append_log("[Safety] Restart requested from initial state.")
        if not self.serial_manager.is_connected:
            self.process_running = False
            self.safety_panel.set_status("E-Stop cleared. Connect Arduino first", critical=True)
            self._update_run_controls()
            return
        if REQUIRE_LINEAR_HOME_FOR_PROCESS and not self._ensure_linear_ready("Restart"):
            self.process_running = False
            self._update_run_controls()
            return
        self.process_running = True
        self.safety_panel.set_status("System Healthy", critical=False)
        self.align_module.set_exposure_value(0, "Ready")
        self.state_manager.set_state(ProcessState.ALIGNING)
        self._stop_jog_immediately()
        self._update_run_controls()
        self._start_auto_align()

    # 타이머와 내부 상태를 정지시키는 공통 정지 함수입니다.
    def _stop_all_motion(self, status_text, critical=False):
        self.process_running = False
        self.is_auto_aligning = False
        self.is_motor_busy = False
        self.auto_align_stable_count = 0
        self.auto_align_x_stable_count = 0
        self.auto_align_phase = "x"
        self.x_align_continuous_active = False
        self.x_align_active_command = None
        self.x_align_active_speed = 0.0
        self.r_align_continuous_active = False
        self.r_align_active_command = None
        self.r_align_active_speed = 0.0
        self.r_zero_crossed = False
        self.r_last_stop_error_sign = 0
        self.auto_align_timer.stop()
        self.exposure_timer.stop()
        self.jog_hold_timer.stop()
        self.pending_jog_command = None
        self.continuous_jog_active = False
        self.safety_panel.set_status(status_text, critical=critical)
        self._update_run_controls()

    # 현재 사이클만 중단하고 정렬 대기 상태로 되돌립니다.
    def _stop_process(self):
        if self.emergency_stop_active:
            return
        if self.serial_manager.is_connected:
            self.serial_manager.send_command("JOG_STOP")
        self._stop_all_motion("Cycle stopped", critical=False)
        self.align_module.set_exposure_value(0, "Ready")
        self.state_manager.set_state(ProcessState.ALIGNING)
        self.debug_panel.append_log("[Process] Cycle stopped by operator.")

    # E-Stop 입력 시 즉시 공정을 멈추고 인터락 상태로 전환합니다.
    def _on_emergency_stop(self):
        if self.emergency_stop_active:
            return
        self.emergency_stop_active = True
        if self.serial_manager.is_connected:
            self.serial_manager.send_command("EMERGENCY_STOP")
        self._stop_all_motion("Emergency stop active", critical=True)
        self.align_module.set_exposure_value(0, "E-Stop Active")
        self.debug_panel.append_log("[Safety] Emergency stop activated.")
        self._update_run_controls()

    # 자동 정렬 루프를 시작합니다.
    def _start_auto_align(self, start_phase="x", source="Auto"):
        if self.emergency_stop_active:
            return
        if not self._ensure_serial_connected("Auto align"):
            return
        self.align_sequence_source = source
        self.is_auto_aligning = True
        self.is_motor_busy = False
        self.auto_align_stable_count = 0
        self.auto_align_x_stable_count = 0
        self.auto_align_phase = start_phase
        self.x_align_continuous_active = False
        self.x_align_active_command = None
        self.x_align_active_speed = 0.0
        self.r_align_continuous_active = False
        self.r_align_active_command = None
        self.r_align_active_speed = 0.0
        self.r_zero_crossed = False
        self.r_last_stop_error_sign = 0
        self._update_run_controls()
        self.state_manager.set_state(ProcessState.ALIGNING)
        self.debug_panel.append_log(f"[Align] {source} align loop started. Phase: {start_phase.upper()} -> R")
        if not self.auto_align_timer.isActive():
            self.auto_align_timer.start(AUTO_ALIGN_POLL_MS)

    # 주기적으로 현재 각도를 읽어 자동 보정 명령을 생성합니다.
    def _auto_align_loop(self):
        if not self.is_auto_aligning:
            return
        if not self.serial_manager.is_connected:
            self._stop_all_motion("Arduino disconnected", critical=True)
            self.align_module.set_exposure_value(0, "Connect Arduino")
            self.debug_panel.append_log("[Safety] Auto align stopped because Arduino is disconnected.")
            return

        if self.is_motor_busy:
            return

        if self.auto_align_phase == "x":
            x_error_abs = abs(self.current_x_alignment_error_px)
            if x_error_abs <= AUTO_ALIGN_X_TARGET_PX:
                if self.x_align_continuous_active:
                    self._stop_x_alignment_motion()
                    return
                self.auto_align_x_stable_count += 1
                if self.auto_align_x_stable_count < AUTO_ALIGN_X_STABLE_FRAMES:
                    return
                self.auto_align_phase = "r"
                self.auto_align_x_stable_count = 0
                self.r_zero_crossed = False
                self.r_last_stop_error_sign = 0
                self.debug_panel.append_log(
                    f"[Align] X alignment complete. Center error: {self.current_x_alignment_error_px:.1f} px"
                )
                return

            self.auto_align_x_stable_count = 0
            self._execute_x_alignment_step(self.current_x_alignment_error_px, self.align_sequence_source)
            return

        stop_error_abs = abs(self.current_alignment_stop_error)
        self._update_r_zero_cross_state(self.current_alignment_stop_error)

        # 연속 회전 중 목표를 넘어섰다면 즉시 정지해 되받아치는 양을 줄입니다.
        if (
            self.r_align_continuous_active
            and not self.current_is_upside_down
            and self._has_r_crossed_target(self.current_alignment_stop_error)
        ):
            self._stop_r_alignment_motion()
            return

        if not self.current_is_upside_down and stop_error_abs <= AUTO_ALIGN_ZERO_LOCK_DEG:
            if self.r_align_continuous_active:
                self._stop_r_alignment_motion()
                return
            self.auto_align_stable_count += 1
            if self.auto_align_stable_count < AUTO_ALIGN_STABLE_FRAMES:
                return
            self.is_auto_aligning = False
            self.auto_align_timer.stop()
            self._update_run_controls()
            self.debug_panel.append_log(
                f"[Align] {self.align_sequence_source} align complete. X error: {self.current_x_alignment_error_px:.1f} px, angle: {self.current_alignment_error:.2f} deg"
            )
            if self.process_running:
                self._start_exposure()
            return

        if not self.current_is_upside_down and stop_error_abs <= AUTO_ALIGN_RELEASE_DEG:
            if self.r_align_continuous_active:
                self._stop_r_alignment_motion()
                return
            self.auto_align_stable_count = 0
            return

        if not self.current_is_upside_down and self.r_zero_crossed:
            self.auto_align_stable_count = 0
            self._start_zero_lock_alignment(self.current_alignment_stop_error)
            return

        self.auto_align_stable_count = 0
        self._execute_r_alignment_step(
            self.current_alignment_error,
            self.current_alignment_stop_error,
            self.align_sequence_source,
        )

    # 각도 오차 크기에 따라 보정량과 속도를 계산합니다.
    def _calculate_alignment_command(self, error_deg):
        error_abs = abs(error_deg)
        base_speed = self.settings["align_speed"]
        if error_abs > 15.0:
            correction = error_deg * 0.28
            speed = max(2.4, base_speed * 0.55)
        elif error_abs > 7.0:
            correction = error_deg * 0.20
            speed = max(1.8, base_speed * 0.38)
        elif error_abs > 3.0:
            correction = error_deg * 0.12
            speed = max(1.2, base_speed * 0.24)
        elif error_abs > AUTO_ALIGN_RELEASE_DEG:
            correction = error_deg * 0.07
            speed = max(0.8, base_speed * 0.14)
        else:
            correction = error_deg * 0.04
            speed = max(0.6, base_speed * 0.10)
        correction = max(-6.0, min(6.0, correction))
        if abs(correction) < 0.03:
            correction = 0.03 if correction >= 0 else -0.03
        return correction, speed

    # R축은 목표에 가까워질수록 속도를 단계적으로 낮춰 관성으로 지나치지 않게 합니다.
    # speedToDelay()가 0~100 범위를 기대하므로, 여기서도 의미 있는 퍼센트값으로 계산합니다.
    def _calculate_r_alignment_command(self, control_error_deg, stop_error_deg):
        error_abs = abs(stop_error_deg)
        base_speed = max(2.0, float(self.settings["align_speed"]))

        if error_abs > 120.0:
            speed, mode = max(5.0, base_speed * 1.00), "recovery"
        elif error_abs > 45.0:
            speed, mode = max(3.6, base_speed * 0.65), "coarse"
        elif error_abs > 18.0:
            speed, mode = max(2.2, base_speed * 0.38), "mid"
        elif error_abs > 8.0:
            speed, mode = max(1.1, base_speed * 0.18), "fine"
        elif error_abs > 3.0:
            speed, mode = max(0.45, base_speed * 0.08), "slow"
        else:
            speed, mode = max(0.18, base_speed * 0.035), "ultra_slow"

        if error_abs <= AUTO_ALIGN_SLOWDOWN_DEG:
            speed *= 0.5
        return speed, mode

    # R축 오차가 0도를 통과했는지 추적해, 이후에는 초저속 보정만 허용하도록 합니다.
    def _update_r_zero_cross_state(self, stop_error_deg):
        if self.current_is_upside_down:
            self.r_zero_crossed = False
            self.r_last_stop_error_sign = 0
            return

        if abs(stop_error_deg) <= AUTO_ALIGN_ZERO_LOCK_DEG:
            return

        current_sign = 1 if stop_error_deg > 0 else -1
        if self.r_last_stop_error_sign != 0 and current_sign != self.r_last_stop_error_sign:
            self.r_zero_crossed = True
        self.r_last_stop_error_sign = current_sign

    # 웨이퍼 중심의 X 오차 크기에 따라 조그 속도와 시간을 계산합니다.
    def _calculate_x_alignment_command(self, x_error_px):
        error_abs = abs(x_error_px)
        base_speed = self.settings["jog_speed"]
        if error_abs > AUTO_ALIGN_X_FINE_PX:
            return max(35.0, base_speed), "coarse"
        return max(8.0, base_speed * 0.20), "fine"

    # X축을 먼저 맞추는 자동 얼라인 단계입니다.
    def _execute_x_alignment_step(self, x_error_px, source):
        if not self._ensure_serial_connected(f"{source} x align"):
            self._stop_all_motion("Connect Arduino first", critical=True)
            return False
        command = "JOG_START_X_NEG" if x_error_px > 0 else "JOG_START_X_POS"
        speed, motion_mode = self._calculate_x_alignment_command(x_error_px)
        if (
            self.x_align_continuous_active
            and self.x_align_active_command == command
            and abs(self.x_align_active_speed - speed) < 0.5
        ):
            return True
        self.debug_panel.append_log(
            f"[Align] {source} X correction -> {command}:{speed:.1f} ({motion_mode})"
        )
        if self.serial_manager.send_command(f"{command}:{speed:.1f}"):
            self.x_align_continuous_active = True
            self.x_align_active_command = command
            self.x_align_active_speed = speed
            return True
        self._stop_all_motion("Connect Arduino first", critical=True)
        return False

    # 자동/수동 얼라인이 공통으로 사용하는 실제 보정 명령 실행 함수입니다.
    def _execute_alignment_step(self, error_deg, source):
        if not self._ensure_serial_connected(f"{source} align"):
            self._stop_all_motion("Connect Arduino first", critical=True)
            return False
        if abs(error_deg) <= AUTO_ALIGN_CREEP_THRESHOLD_DEG:
            self._start_creep_alignment(error_deg)
            return True

        correction_deg, speed = self._calculate_alignment_command(error_deg)
        # 펌웨어의 ALIGN 부호와 UI 상태 문구 부호를 일치시키기 위해 반대로 전송합니다.
        command = f"ALIGN:{-correction_deg:.2f}:{speed:.1f}"
        self.debug_panel.append_log(f"[Align] {source} correction -> {command}")
        if self.serial_manager.send_command(command):
            self.is_motor_busy = True
            return True
        self._stop_all_motion("Connect Arduino first", critical=True)
        return False

    # R축도 연속 회전으로 부드럽게 접근시키며, 위쪽 키 정렬이 끝날 때만 멈춥니다.
    def _execute_r_alignment_step(self, error_deg, stop_error_deg, source):
        if not self._ensure_serial_connected(f"{source} align"):
            self._stop_all_motion("Connect Arduino first", critical=True)
            return False
        # 비전 상태 문구와 실제 회전 방향을 일치시킵니다.
        # 양수 오차면 "ROTATE CCW", 음수 오차면 "ROTATE CW"가 되도록 맞춥니다.
        # 회전 방향은 평활값이 아니라 현재 프레임의 실제 오차(raw)를 우선 따라가야
        # 목표를 넘어선 뒤에도 한쪽 방향으로 오래 끌려가지 않습니다.
        direction_error = stop_error_deg if abs(stop_error_deg) >= 0.05 else error_deg
        command = "JOG_START_CCW" if direction_error > 0 else "JOG_START_CW"
        speed, motion_mode = self._calculate_r_alignment_command(error_deg, stop_error_deg)
        if (
            self.r_align_continuous_active
            and self.r_align_active_command == command
            and abs(self.r_align_active_speed - speed) < 0.05
        ):
            return True
        self.debug_panel.append_log(
            f"[Align] {source} R correction -> {command}:{speed:.2f} ({motion_mode}, raw={stop_error_deg:.2f}, smooth={error_deg:.2f})"
        )
        if self.serial_manager.send_command(f"{command}:{speed:.2f}"):
            self.r_align_continuous_active = True
            self.r_align_active_command = command
            self.r_align_active_speed = speed
            return True
        self._stop_all_motion("Connect Arduino first", critical=True)
        return False

    # 현재 연속 회전 방향 기준으로 목표를 이미 지나쳤는지 확인합니다.
    # 이 값을 사용해 바로 정지시키면 0도를 통과한 뒤 오래 끌려가는 현상을 줄일 수 있습니다.
    def _has_r_crossed_target(self, stop_error_deg):
        cross_margin = max(AUTO_ALIGN_TARGET_DEG * 0.35, 0.20)
        if self.r_align_active_command == "JOG_START_CCW" and stop_error_deg < -cross_margin:
            return True
        if self.r_align_active_command == "JOG_START_CW" and stop_error_deg > cross_margin:
            return True
        return False

    # 고정 각도 펄스를 보내는 공통 함수입니다.
    # 수동 R 탭과 자동 얼라인의 미세 보정이 같은 각도값을 공유하도록 묶었습니다.
    def _send_r_pulse_alignment(self, error_deg, speed, source_label):
        if not self._ensure_serial_connected(source_label):
            self._stop_all_motion("Connect Arduino first", critical=True)
            return False

        # 펌웨어의 ALIGN 부호는 비전 상태 문구와 반대이므로 여기서 한 번 뒤집어 보냅니다.
        # 양수 오차(ROTATE CCW)면 음수 각도를 보내야 실제로 CCW 쪽 보정이 됩니다.
        pulse_deg = -R_JOG_TAP_DEG if error_deg > 0 else R_JOG_TAP_DEG
        command = f"ALIGN:{pulse_deg:.2f}:{speed:.1f}"
        self.debug_panel.append_log(
            f"[Align] {source_label} pulse -> {command} (target error={error_deg:.2f})"
        )
        if self.serial_manager.send_command(command):
            self.is_motor_busy = True
            return True
        self._stop_all_motion("Connect Arduino first", critical=True)
        return False

    # 0도 부근을 한 번 통과한 뒤에는 연속 회전 대신 고정 각도 펄스만 반복합니다.
    # 이렇게 해야 0도 근처에서 CW/CCW가 빠르게 뒤집히며 체터링하는 현상을 줄일 수 있습니다.
    def _start_zero_lock_alignment(self, stop_error_deg):
        if abs(stop_error_deg) <= AUTO_ALIGN_ZERO_LOCK_DEG:
            return
        speed = max(0.8, self.settings["align_speed"] * 0.10)
        self._send_r_pulse_alignment(stop_error_deg, speed, "Zero-lock")

    # 목표 근처에서는 저속 creep 방식으로 미세 접근합니다.
    def _start_creep_alignment(self, error_deg):
        speed = max(1.2, self.settings["align_speed"] * 0.18)
        self._send_r_pulse_alignment(error_deg, speed, "Fine approach")

    # X축 연속 얼라인 동작을 멈추고 다음 정렬 판단을 허용합니다.
    def _stop_x_alignment_motion(self):
        if self.serial_manager.is_connected:
            self.serial_manager.send_command("JOG_STOP")
        self.x_align_continuous_active = False
        self.x_align_active_command = None
        self.x_align_active_speed = 0.0
        self.is_motor_busy = True
        QTimer.singleShot(AUTO_ALIGN_CREEP_SETTLE_MS, self._mark_motion_done)

    # creep 동작을 멈추고 안정화 대기 단계로 넘어갑니다.
    def _stop_creep_alignment(self):
        if self.serial_manager.is_connected:
            self.serial_manager.send_command("JOG_STOP")
        QTimer.singleShot(AUTO_ALIGN_CREEP_SETTLE_MS, self._mark_motion_done)

    # 연속 R 정렬 동작을 멈추고 다음 판단 전까지 잠시 안정화를 기다립니다.
    def _stop_r_alignment_motion(self):
        if self.serial_manager.is_connected:
            self.serial_manager.send_command("JOG_STOP")
        self.r_align_continuous_active = False
        self.r_align_active_command = None
        self.r_align_active_speed = 0.0
        self.is_motor_busy = True
        QTimer.singleShot(AUTO_ALIGN_CREEP_SETTLE_MS, self._mark_motion_done)

    # 모터가 멈춘 뒤 다음 자동 보정 판단을 허용합니다.
    def _mark_motion_done(self):
        self.is_motor_busy = False

    # 수동 얼라인 버튼은 자동 얼라인과 같은 계산 로직을 공유합니다.
    def _manual_align(self):
        if not self._ensure_serial_connected("Manual align"):
            return
        self._release_emergency_for_manual_control("Manual align")
        if REQUIRE_LINEAR_HOME_FOR_PROCESS and not self._ensure_linear_ready("Manual align"):
            return
        self.process_running = False
        self.is_auto_aligning = False
        self.is_motor_busy = False
        self._update_run_controls()
        start_phase = "x" if abs(self.current_x_alignment_error_px) > AUTO_ALIGN_X_TARGET_PX else "r"
        if (
            start_phase == "r"
            and not self.current_is_upside_down
            and abs(self.current_alignment_stop_error) <= AUTO_ALIGN_TARGET_DEG
        ):
            self.debug_panel.append_log("[Align] Manual align skipped. Already within target.")
            self.safety_panel.set_status("Alignment within tolerance", critical=False)
            return
        self._start_auto_align(start_phase=start_phase, source="Manual")

    # 조그 버튼을 눌렀을 때 탭/홀드 판정을 준비합니다.
    def _start_manual_jog(self, command):
        if not self._ensure_serial_connected("Jog"):
            return
        self._release_emergency_for_manual_control("Jog")
        if not self._can_use_jog_command(command):
            return
        self.is_motor_busy = False
        self.pending_jog_command = command
        self.continuous_jog_active = False
        self.jog_hold_timer.start(MANUAL_JOG_HOLD_MS)

    # 0.3초 이상 누른 경우 연속 조그를 시작합니다.
    def _begin_continuous_jog(self):
        command = self.pending_jog_command
        command_map = {
            "JOG_X_POS": "JOG_START_X_POS",
            "JOG_X_NEG": "JOG_START_X_NEG",
            "JOG_Y_POS": "JOG_START_Y_POS",
            "JOG_Y_NEG": "JOG_START_Y_NEG",
            "JOG_R_POS": "JOG_START_CW",
            "JOG_R_NEG": "JOG_START_CCW",
        }
        if command not in command_map:
            return
        speed = self.settings["rotation_speed"] if command.startswith("JOG_R") else self.settings["jog_speed"]
        mapped = command_map[command]
        if self.serial_manager.send_command(f"{mapped}:{speed:.1f}"):
            self.continuous_jog_active = True
            self.debug_panel.append_log(f"[Jog] Continuous {command} started.")

    # 현재 진행 중인 조그를 즉시 중단합니다.
    def _stop_jog_immediately(self):
        self.jog_hold_timer.stop()
        if self.continuous_jog_active and self.serial_manager.is_connected:
            self.serial_manager.send_command("JOG_STOP")
        if self.x_align_continuous_active and self.serial_manager.is_connected:
            self.serial_manager.send_command("JOG_STOP")
        if self.r_align_continuous_active and self.serial_manager.is_connected:
            self.serial_manager.send_command("JOG_STOP")
        self.pending_jog_command = None
        self.continuous_jog_active = False
        self.x_align_continuous_active = False
        self.x_align_active_command = None
        self.x_align_active_speed = 0.0
        self.r_align_continuous_active = False
        self.r_align_active_command = None
        self.r_align_active_speed = 0.0

    # 버튼을 떼면 탭 조그 또는 연속 조그 종료를 처리합니다.
    def _stop_manual_jog(self):
        command = self.pending_jog_command
        if command is None:
            return

        if self.jog_hold_timer.isActive():
            self.jog_hold_timer.stop()
            if command in {"JOG_R_POS", "JOG_R_NEG"} and self.serial_manager.is_connected:
                speed = max(2.0, self.settings["rotation_speed"])
                error_sign = 1.0 if command == "JOG_R_POS" else -1.0
                self._send_r_pulse_alignment(error_sign, speed, "Jog tap")
            elif command in {"JOG_X_POS", "JOG_X_NEG", "JOG_Y_POS", "JOG_Y_NEG"} and self.serial_manager.is_connected:
                pulse_map = {
                    "JOG_X_POS": "JOG_START_X_POS",
                    "JOG_X_NEG": "JOG_START_X_NEG",
                    "JOG_Y_POS": "JOG_START_Y_POS",
                    "JOG_Y_NEG": "JOG_START_Y_NEG",
                }
                if self.serial_manager.send_command(f"{pulse_map[command]}:{self.settings['jog_speed']:.1f}"):
                    QTimer.singleShot(120, self._stop_jog_immediately)
        elif self.continuous_jog_active and self.serial_manager.is_connected:
            self.serial_manager.send_command("JOG_STOP")
            self.debug_panel.append_log(f"[Jog] Continuous {command} stopped.")

        self.pending_jog_command = None
        self.continuous_jog_active = False

    # 자동 정렬 완료 후 노광 공정을 시작합니다.
    def _start_exposure(self):
        if self.emergency_stop_active:
            return
        if not self._ensure_serial_connected("Exposure"):
            return
        if REQUIRE_LINEAR_HOME_FOR_PROCESS and not self._ensure_linear_ready("Exposure"):
            return
        self.process_running = True
        self._update_run_controls()
        self.state_manager.set_state(ProcessState.EXPOSING)
        self.exposure_progress = 0
        self.align_module.set_exposure_value(0, "Exposure 0%")
        self.debug_panel.append_log("[Process] Exposure sequence started.")
        self.exposure_timer.start(100)

    # 노광 진행률을 시간 기반으로 갱신합니다.
    def _advance_exposure(self):
        duration_ms = max(500, int(self.settings["exposure_time_sec"] * 1000))
        step = max(1, int((100 * self.exposure_timer.interval()) / duration_ms))
        self.exposure_progress += step
        progress = min(self.exposure_progress, 100)
        self.align_module.set_exposure_value(progress, f"Exposure {progress}%")
        if progress < 100:
            return
        self.exposure_timer.stop()
        self.align_module.set_exposure_value(100, "Exposure Complete")
        self.debug_panel.append_log("[Process] Exposure finished. Moving wafer to inspector.")
        self.state_manager.set_state(ProcessState.MOVING)
        QTimer.singleShot(800, self._go_to_inspection)

    # 노광 후 검사 단계로 화면과 상태를 넘깁니다.
    def _go_to_inspection(self):
        if self.emergency_stop_active:
            return
        self.state_manager.set_state(ProcessState.INSPECTING)
        self.debug_panel.append_log("[Process] Waiting for inspection decision.")

    # 검사 결과를 받은 뒤 ET-Test 단계로 연결합니다.
    def _on_inspection_complete(self, passed):
        if self.emergency_stop_active:
            return
        self.last_inspection_result = passed
        self.debug_panel.append_log(f"[Process] Inspection complete: {'PASS' if passed else 'FAIL'}")
        self.state_manager.set_state(ProcessState.ET_TEST)
        self.et_test_module.run_test(passed)
        self.debug_panel.append_log("[Process] ET-Test page opened.")

    # ET-Test 맵을 수동으로 갱신할 때 호출됩니다.
    def _run_et_test_manually(self):
        if not self._ensure_serial_connected("ET-Test"):
            return
        if REQUIRE_LINEAR_HOME_FOR_PROCESS and not self._ensure_linear_ready("ET-Test"):
            return
        if self.state_manager.current_state != ProcessState.ET_TEST:
            self.state_manager.set_state(ProcessState.ET_TEST)
        self.et_test_module.run_test(self.last_inspection_result)
        self.debug_panel.append_log("[ET-Test] Contact map updated.")

    # ET-Test 완료 후 정리 단계로 넘어갑니다.
    def _complete_et_test(self):
        if self.state_manager.current_state != ProcessState.ET_TEST:
            return
        self.debug_panel.append_log("[Process] ET-Test complete. Sorting wafer.")
        self.state_manager.set_state(ProcessState.SORTING)
        QTimer.singleShot(700, self._finish_cycle)

    # 한 사이클을 종료하고 다음 웨이퍼 대기 상태로 복귀합니다.
    def _finish_cycle(self):
        self.process_running = False
        self.is_auto_aligning = False
        self.is_motor_busy = False
        self._update_run_controls()
        self.state_manager.set_state(ProcessState.ALIGNING)
        self.debug_panel.append_log("[Process] Cycle complete. Ready for next wafer.")

    # 상태 변경 시 단계 바, 화면, 상태 바를 함께 갱신합니다.
    def _on_state_changed(self, state):
        self.last_active_state = state
        self.step_bar.update_state(state)
        self._switch_page(state)
        self._update_status_bar()

    # 인터락 상태에 따라 조작 위젯들을 일괄 활성/비활성 처리합니다.
    def _set_controls_enabled(self, enabled):
        serial_widgets = {
            self.serial_bar.connect_button,
            self.serial_bar.disconnect_button,
            self.serial_bar.refresh_button,
            self.serial_bar.port_combo,
            self.serial_bar.settings_button,
        }
        for widget in self._control_widgets:
            if not enabled and widget in serial_widgets:
                widget.setEnabled(True)
                continue
            widget.setEnabled(enabled)
        self.safety_panel.start_button.setEnabled(True)
        self.safety_panel.stop_button.setEnabled(False)
        self.safety_panel.restart_button.setEnabled(True)
        self.safety_panel.estop_button.setEnabled(True)
        self._update_run_controls()

    # Start/Resume/Stop/Restart 버튼 상태를 현재 공정에 맞춰 맞춥니다.
    def _update_run_controls(self):
        if self.emergency_stop_active:
            self.safety_panel.start_button.setText("Resume")
            self.safety_panel.start_button.setEnabled(True)
            self.safety_panel.stop_button.setEnabled(False)
            self.safety_panel.restart_button.setEnabled(True)
            self.align_module.linear_home_button.setEnabled(
                self.serial_manager.is_connected and self._has_required_linear_home_axis()
            )
            self.align_module.manual_align_button.setEnabled(
                self.serial_manager.is_connected
                and (
                    (not REQUIRE_LINEAR_HOME_FOR_PROCESS)
                    or (not self._has_required_linear_home_axis())
                    or self.linear_stage_homed
                )
            )
            self.align_module.set_axis_enabled("JOG_X_POS", self.serial_manager.is_connected and ENABLE_X_STAGE)
            self.align_module.set_axis_enabled("JOG_X_NEG", self.serial_manager.is_connected and ENABLE_X_STAGE)
            self.align_module.set_axis_enabled("JOG_Y_POS", self.serial_manager.is_connected and ENABLE_Y_STAGE)
            self.align_module.set_axis_enabled("JOG_Y_NEG", self.serial_manager.is_connected and ENABLE_Y_STAGE)
            self.align_module.set_axis_enabled("JOG_R_POS", self.serial_manager.is_connected and ENABLE_R_STAGE)
            self.align_module.set_axis_enabled("JOG_R_NEG", self.serial_manager.is_connected and ENABLE_R_STAGE)
            self.inspect_module.pass_button.setEnabled(False)
            self.inspect_module.fail_button.setEnabled(False)
            self.et_test_module.run_button.setEnabled(False)
            self.et_test_module.complete_button.setEnabled(False)
            self.et_test_module.clear_button.setEnabled(False)
            return

        self.safety_panel.start_button.setText("Start")
        linear_ready = (
            (not REQUIRE_LINEAR_HOME_FOR_PROCESS)
            or (not self._has_required_linear_home_axis())
            or self.linear_stage_homed
        )
        if self.process_running or self.is_auto_aligning:
            self.safety_panel.start_button.setEnabled(False)
            self.safety_panel.stop_button.setEnabled(True)
        else:
            ready = self.serial_manager.is_connected and linear_ready and not self.linear_homing_active
            self.safety_panel.start_button.setEnabled(ready)
            self.safety_panel.stop_button.setEnabled(False)
        self.safety_panel.restart_button.setEnabled(
            self.serial_manager.is_connected and linear_ready and not self.linear_homing_active
        )

        control_ready = self.serial_manager.is_connected and linear_ready and not self.linear_homing_active
        motion_ready = self.serial_manager.is_connected and not (self.process_running or self.is_auto_aligning)
        self.align_module.linear_home_button.setEnabled(
            self.serial_manager.is_connected
            and self._has_required_linear_home_axis()
            and not self.linear_homing_active
            and not self.process_running
            and not self.is_auto_aligning
        )
        self.align_module.manual_align_button.setEnabled(
            motion_ready
            and (
                (not REQUIRE_LINEAR_HOME_FOR_PROCESS)
                or (not self._has_required_linear_home_axis())
                or linear_ready
            )
        )
        self.align_module.set_axis_enabled("JOG_X_POS", motion_ready and ENABLE_X_STAGE)
        self.align_module.set_axis_enabled("JOG_X_NEG", motion_ready and ENABLE_X_STAGE)
        self.align_module.set_axis_enabled("JOG_Y_POS", motion_ready and ENABLE_Y_STAGE)
        self.align_module.set_axis_enabled("JOG_Y_NEG", motion_ready and ENABLE_Y_STAGE)
        self.align_module.set_axis_enabled("JOG_R_POS", motion_ready and ENABLE_R_STAGE)
        self.align_module.set_axis_enabled("JOG_R_NEG", motion_ready and ENABLE_R_STAGE)
        self.inspect_module.pass_button.setEnabled(control_ready)
        self.inspect_module.fail_button.setEnabled(control_ready)
        self.et_test_module.run_button.setEnabled(control_ready)
        self.et_test_module.complete_button.setEnabled(control_ready)
        self.et_test_module.clear_button.setEnabled(control_ready)

    # 하단 상태 바에 연결 포트, 공정 상태, 현재 각도 오차를 표시합니다.
    def _update_status_bar(self):
        port_text = self.serial_manager.port if self.serial_manager.is_connected else "Disconnected"
        self.status_bar.showMessage(
            f"{port_text} @ {DEFAULT_BAUDRATE} | State: {self.state_manager.current_state.name} | X Error: {self.current_x_alignment_error_px:.1f}px | Angle Error: {self.current_alignment_error:.2f}"
        )

    # 창 종료 시 스레드와 연결을 안전하게 정리합니다.
    def closeEvent(self, event):
        self.exposure_timer.stop()
        self.auto_align_timer.stop()
        self.serial_poll_timer.stop()
        self.jog_hold_timer.stop()
        self._save_splitter_state()
        self.serial_manager.disconnect_port()
        for thread in (self.aligner_thread, self.inspector_thread):
            if thread and thread.isRunning():
                thread.stop()
        event.accept()


# Qt 애플리케이션을 생성하고 메인 윈도우를 실행합니다.
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
