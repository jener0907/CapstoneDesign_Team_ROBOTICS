# 공정 전체에서 공통으로 쓰는 핵심 로직 모음입니다.
# 상태 머신, 시리얼, 카메라 스레드, 각도 계산을 여기서 관리합니다.
import math
import os
from enum import Enum, auto

import cv2
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtGui import QImage

from .config import (
    ALIGNER_CONFIDENCE,
    ALIGNER_MODEL_PATH,
    ALIGN_CAMERA_OFFSET_DEG,
    ALIGN_ROTATION_SIGN,
    ALIGN_TOLERANCE_DEG,
    ANGLE_SMOOTHING_ALPHA,
    CAMERA_FRAME_INTERVAL_MS,
    DEFAULT_BAUDRATE,
)

try:
    import supervision as sv
    from ultralytics import YOLO
except Exception:
    sv = None
    YOLO = None


# 공정 단계를 코드 상수로 통일하기 위한 Enum입니다.
class ProcessState(Enum):
    IDLE = auto()
    ALIGNING = auto()
    EXPOSING = auto()
    MOVING = auto()
    INSPECTING = auto()
    ET_TEST = auto()
    SORTING = auto()


# 현재 공정 상태를 저장하고, 바뀌면 UI에 알리는 관리자입니다.
class StateManager(QObject):
    state_changed = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._state = ProcessState.IDLE

    @property
    def current_state(self):
        return self._state

    # 상태가 실제로 바뀌었을 때만 시그널을 발생시킵니다.
    def set_state(self, state):
        if state == self._state:
            return
        self._state = state
        self.state_changed.emit(state)


# 아두이노와의 연결/전송/수신을 담당하는 시리얼 통신 클래스입니다.
class SerialManager(QObject):
    connection_changed = pyqtSignal(bool, str)
    log_signal = pyqtSignal(str)

    def __init__(self, baudrate=DEFAULT_BAUDRATE):
        super().__init__()
        self.baudrate = baudrate
        self.port = ""
        self.serial_conn = None
        self.is_connected = False
        try:
            import serial  # pylint: disable=import-outside-toplevel
            from serial.tools import list_ports  # pylint: disable=import-outside-toplevel
        except Exception:
            serial = None
            list_ports = None
        self._serial_module = serial
        self._list_ports_module = list_ports

    # 현재 시스템에서 연결 가능한 시리얼 포트를 조회합니다.
    def available_ports(self):
        if self._list_ports_module is None:
            return []
        try:
            return [p.device for p in self._list_ports_module.comports()]
        except Exception:
            return []

    # 선택된 포트로 연결을 시도하고 결과를 시그널로 전달합니다.
    def connect_port(self, port):
        if self._serial_module is None:
            self.log_signal.emit("[Serial] pyserial not installed.")
            self.connection_changed.emit(False, "Offline")
            return

        self.port = port
        try:
            self.serial_conn = self._serial_module.Serial(port, self.baudrate, timeout=0.05)
            self.is_connected = True
            self.log_signal.emit(f"[Serial] Connected to {port}")
            self.connection_changed.emit(True, port)
        except Exception as exc:
            self.serial_conn = None
            self.is_connected = False
            self.log_signal.emit(f"[Serial] Connection failed ({port}): {exc}")
            self.connection_changed.emit(False, port)

    # 기존 연결이 있다면 안전하게 닫습니다.
    def disconnect_port(self):
        if self.serial_conn:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        self.serial_conn = None
        self.is_connected = False
        self.log_signal.emit("[Serial] Disconnected")
        self.connection_changed.emit(False, self.port or "Disconnected")

    # 장비 제어 명령을 아두이노로 전송합니다.
    # 연결이 없으면 실제 전송 대신 차단 로그만 남깁니다.
    def send_command(self, command):
        command = f"{str(command).strip()}\n"
        if self.is_connected and self.serial_conn:
            try:
                self.serial_conn.write(command.encode("utf-8"))
                self.log_signal.emit(f"[Serial] Sent: {command.strip()}")
                return True
            except Exception as exc:
                self.log_signal.emit(f"[Serial] Send error: {exc}")
                self.disconnect_port()
                return False
        self.log_signal.emit(f"[Serial] Blocked while disconnected: {command.strip()}")
        return False

    # 아두이노가 보낸 한 줄 응답을 읽습니다.
    def read_line(self):
        if self.is_connected and self.serial_conn and self.serial_conn.in_waiting > 0:
            try:
                line = self.serial_conn.readline().decode("utf-8", errors="ignore").strip()
                return line or None
            except Exception:
                return None
        return None


# 카메라 프레임 캡처와 얼라인 비전 추론을 별도 스레드에서 수행합니다.
class CameraThread(QThread):
    frame_ready = pyqtSignal(str, object, object)
    camera_error = pyqtSignal(str)

    def __init__(self, role, camera_index, model_path=None, confidence=ALIGNER_CONFIDENCE, parent=None):
        super().__init__(parent)
        self.role = role
        self.camera_index = camera_index
        self.model_path = model_path
        self.confidence = confidence
        self._running = True
        self.model = None
        self._smoothed_angle = None
        self.box_annotator = sv.BoxAnnotator() if sv else None
        self.label_annotator = sv.LabelAnnotator() if sv else None

    # 카메라를 열고 프레임을 계속 읽어 UI 스레드로 전달합니다.
    # 1번 카메라가 없으면 자동으로 0번 카메라를 시도합니다.
    def run(self):
        if self.role == "Aligner":
            self._load_model()

        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.camera_index = 0
            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                self.camera_error.emit("camera_not found")
                return

        while self._running:
            ok, frame = cap.read()
            if not ok:
                self.camera_error.emit("camera_not found")
                self.msleep(100)
                continue

            processed = frame.copy()
            metadata = {}
            if self.role == "Aligner":
                processed, metadata = self._process_aligner_frame(processed)

            self.frame_ready.emit(self.role, processed, metadata)
            self.msleep(CAMERA_FRAME_INTERVAL_MS)

        cap.release()

    # 스레드를 안전하게 종료합니다.
    def stop(self):
        self._running = False
        self.wait()

    # 얼라인용 YOLO 모델을 한 번만 로드합니다.
    def _load_model(self):
        if YOLO is None or sv is None:
            self.camera_error.emit("[Aligner] ultralytics/supervision import failed.")
            return
        model_path = self.model_path or ALIGNER_MODEL_PATH
        if not os.path.exists(model_path):
            self.camera_error.emit(f"[Aligner] Model not found: {model_path}")
            return
        try:
            self.model = YOLO(model_path)
        except Exception as exc:
            self.camera_error.emit(f"[Aligner] Model load failed: {exc}")

    # 얼라인 프레임에서 Key/Wafer를 찾고 정렬 각도와 상태를 계산합니다.
    # 이 메서드의 결과가 자동 정렬과 수동 얼라인에 공통으로 사용됩니다.
    def _process_aligner_frame(self, frame):
        metadata = {
            "angle_deg": None,
            "angle_raw_deg": None,
            "status_text": "Vision model not ready",
            "error_to_send": 0.0,
            "error_to_stop": 0.0,
            "key_count": 0,
            "wafer_count": 0,
            "is_upside_down": False,
            "wafer_center_x": None,
            "wafer_center_error_px": None,
        }
        if self.model is None or sv is None:
            return frame, metadata

        try:
            results = self.model(frame, conf=self.confidence, verbose=False)[0]
            detections = sv.Detections.from_ultralytics(results)
            annotated = frame.copy()
            annotated = self.box_annotator.annotate(scene=annotated, detections=detections)
            annotated = self.label_annotator.annotate(scene=annotated, detections=detections)

            key_centers = []
            wafer_centers = []
            if results.obb is not None:
                for obb in results.obb:
                    class_id = int(obb.cls[0].item())
                    class_name = self.model.names[class_id]
                    center_x = float(obb.xywhr[0][0].item())
                    center_y = float(obb.xywhr[0][1].item())
                    cv2.circle(annotated, (int(center_x), int(center_y)), 4, (90, 210, 255), -1)
                    if "Key" in class_name or class_id == 0:
                        key_centers.append((center_x, center_y))
                    elif "Wafer" in class_name or class_id == 1:
                        wafer_centers.append((center_x, center_y))

            metadata["key_count"] = len(key_centers)
            metadata["wafer_count"] = len(wafer_centers)
            if wafer_centers:
                wafer_cx = wafer_centers[0][0]
                metadata["wafer_center_x"] = wafer_cx
                metadata["wafer_center_error_px"] = wafer_cx - (frame.shape[1] / 2.0)

            if len(key_centers) == 2:
                key_centers.sort(key=lambda pt: pt[0])
                pt1, pt2 = key_centers
                cv2.line(annotated, (int(pt1[0]), int(pt1[1])), (int(pt2[0]), int(pt2[1])), (120, 200, 255), 2)
                if wafer_centers:
                    wafer_cx, wafer_cy = wafer_centers[0]
                    key_mid_x = (pt1[0] + pt2[0]) / 2.0
                    key_mid_y = (pt1[1] + pt2[1]) / 2.0
                    cv2.circle(annotated, (int(key_mid_x), int(key_mid_y)), 5, (255, 215, 80), -1)
                    vector_dx = key_mid_x - wafer_cx
                    vector_dy = key_mid_y - wafer_cy

                    # 키의 중점이 웨이퍼 중심에서 "위쪽"으로 오도록 만드는 회전 오차를 계산합니다.
                    # 0도는 정확히 위쪽, 양수는 CCW, 음수는 CW로 맞춥니다.
                    # 장비/카메라 설치 방향에 따라 회전 부호가 뒤집힐 수 있으므로
                    # 설정값으로 한 번 더 보정합니다.
                    raw_angle_deg = ALIGN_ROTATION_SIGN * (
                        float(math.degrees(math.atan2(vector_dx, -vector_dy))) - ALIGN_CAMERA_OFFSET_DEG
                    )
                    raw_angle_deg = self._normalize_angle(raw_angle_deg)
                    corrected_angle_deg = self._smooth_angle(raw_angle_deg)
                    corrected_angle_deg = self._normalize_angle(corrected_angle_deg)

                    metadata["angle_raw_deg"] = raw_angle_deg
                    metadata["angle_deg"] = corrected_angle_deg
                    metadata["error_to_send"] = corrected_angle_deg
                    metadata["error_to_stop"] = raw_angle_deg
                    metadata["is_upside_down"] = abs(raw_angle_deg) > 90.0
                else:
                    dx = pt2[0] - pt1[0]
                    dy = pt2[1] - pt1[1]
                    raw_angle_deg = ALIGN_ROTATION_SIGN * float(math.degrees(math.atan2(dy, dx)) - ALIGN_CAMERA_OFFSET_DEG)
                    corrected_angle_deg = self._normalize_line_angle(raw_angle_deg)
                    corrected_angle_deg = self._smooth_angle(corrected_angle_deg)
                    corrected_angle_deg = self._normalize_line_angle(corrected_angle_deg)
                    metadata["angle_raw_deg"] = corrected_angle_deg
                    metadata["angle_deg"] = corrected_angle_deg
                    metadata["error_to_send"] = corrected_angle_deg
                    metadata["error_to_stop"] = corrected_angle_deg

                if wafer_centers:
                    wafer_cy = wafer_centers[0][1]
                    keys_avg_y = (pt1[1] + pt2[1]) / 2.0
                    metadata["is_upside_down"] = keys_avg_y > wafer_cy or metadata["is_upside_down"]

                if metadata["is_upside_down"]:
                    metadata["status_text"] = "UPSIDE DOWN"
                elif abs(corrected_angle_deg) <= ALIGN_TOLERANCE_DEG:
                    metadata["status_text"] = "ALIGNED"
                elif corrected_angle_deg > 0:
                    metadata["status_text"] = "ROTATE CCW"
                else:
                    metadata["status_text"] = "ROTATE CW"
            elif len(key_centers) == 1:
                metadata["status_text"] = "Searching for 2nd key"
            elif len(key_centers) > 2:
                metadata["status_text"] = "Too many keys"
            else:
                metadata["status_text"] = "No align key detected"

            return annotated, metadata
        except Exception as exc:
            metadata["status_text"] = "Inference error"
            self.camera_error.emit(f"[Aligner] Inference failed: {exc}")
            return frame, metadata

    @staticmethod
    # 각도를 -180~180 범위로 정규화합니다.
    def _normalize_angle(angle_deg):
        while angle_deg > 180.0:
            angle_deg -= 360.0
        while angle_deg <= -180.0:
            angle_deg += 360.0
        return angle_deg

    @staticmethod
    # 정렬 키가 만드는 "선"의 각도를 -90~90 범위의 최단 회전값으로 접습니다.
    def _normalize_line_angle(angle_deg):
        normalized = CameraThread._normalize_angle(angle_deg)
        if normalized > 90.0:
            normalized -= 180.0
        elif normalized <= -90.0:
            normalized += 180.0
        return normalized

    # 프레임 간 각도 흔들림을 줄이기 위해 지수 평활을 적용합니다.
    def _smooth_angle(self, angle_deg):
        if self._smoothed_angle is None:
            self._smoothed_angle = angle_deg
            return angle_deg

        delta = self._normalize_angle(angle_deg - self._smoothed_angle)
        self._smoothed_angle = self._normalize_angle(
            self._smoothed_angle + delta * ANGLE_SMOOTHING_ALPHA
        )
        return self._smoothed_angle


# OpenCV 프레임을 Qt에서 표시 가능한 QImage로 변환합니다.
def frame_to_qimage(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    bytes_per_line = ch * w
    return QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
