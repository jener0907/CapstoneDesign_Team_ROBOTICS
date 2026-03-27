# 카메라 인덱스와 프레임 주기를 한곳에서 관리합니다.
ALIGNER_CAMERA_INDEX           = 1
INSPECTOR_CAMERA_INDEX         = 1
CAMERA_FRAME_INTERVAL_MS       = 30

# 현재 실제로 연결해 둔 축만 True로 두면 됩니다.
# 현재 기본값은 X + R 얼라인 테스트 기준입니다.
# Y축까지 연결한 뒤에는 ENABLE_Y_STAGE = True로 다시 바꾸면 됩니다.
ENABLE_X_STAGE                  = True
ENABLE_Y_STAGE                  = False
ENABLE_R_STAGE                  = True
REQUIRE_LINEAR_HOME_FOR_PROCESS = True
# True로 두면 해당 축은 HOME_LINEAR 명령에서 제외됩니다.
# 현재 기본값은 X + R 테스트용이라 Y 홈을 생략하도록 두었습니다.
SKIP_X_HOME                     = False
SKIP_Y_HOME                     = True

# 리니어 스테이지 기구 계산용 설정값입니다.
# steps_per_mm = (1회전당 스텝 수 * 마이크로스텝 * 기어비) / (풀리 톱니수 * 벨트 피치)
# 중요:
# 이 값들은 arduino_tb6600.ino의 linearMotorStepAngleDeg, linearMicrosteps,
# linearGearRatio, linearPulleyTeeth, linearBeltPitchMm와 같아야 합니다.
# 현재 장비에서 풀리/벨트/기어비가 그대로라면, 실제로는 양쪽 마이크로스텝 값만 맞춰도
# mm 표시 오차가 대부분 해결됩니다.
LINEAR_MOTOR_STEP_ANGLE_DEG    = 1.8
LINEAR_MICROSTEPS              = 16
LINEAR_GEAR_RATIO              = 1.0
LINEAR_PULLEY_TEETH            = 20
LINEAR_BELT_PITCH_MM           = 2.0
LINEAR_TRAVEL_MM               = 300.0

# 얼라인 비전 모델과 통신 기본값입니다.
ALIGNER_MODEL_PATH             = "runs/obb/runs/train/wafer_yolov8_model/weights/best.pt"
ALIGNER_CONFIDENCE             = 0.7
DEFAULT_BAUDRATE               = 9600
ALIGN_CAMERA_OFFSET_DEG        = 0.0
ALIGN_ROTATION_SIGN            = -1.0
ANGLE_SMOOTHING_ALPHA          = 0.18

# 정렬 완료 판정과 자동 보정 루프 민감도를 결정합니다.
ALIGN_TOLERANCE_DEG            = 1.0    # 정렬 완료 기준 각도
AUTO_ALIGN_TARGET_DEG          = 1.0    # 자동 보정 목표 각도
AUTO_ALIGN_RELEASE_DEG         = 1.4    # 자동 보정 해제 각도
AUTO_ALIGN_CREEP_THRESHOLD_DEG = 0.5    # 자동 보정 크립 임계 각도
AUTO_ALIGN_SLOWDOWN_DEG        = 5.0    # 10도 이상이면 속도 줄임   
AUTO_ALIGN_ZERO_LOCK_DEG       = 1.0    # 1도 이내면 정렬 완료
AUTO_ALIGN_POLL_MS             = 50     # 50ms 마다 폴링
AUTO_ALIGN_STABLE_FRAMES       = 4      # 4프레임 동안 안정
AUTO_ALIGN_CREEP_SETTLE_MS     = 320    # 320ms 동안 크립
AUTO_ALIGN_X_TARGET_PX         = 18.0   # X축 목표 픽셀
AUTO_ALIGN_X_RELEASE_PX        = 28.0   # X축 해제 픽셀
AUTO_ALIGN_X_STABLE_FRAMES     = 3      # X축 안정 프레임
AUTO_ALIGN_X_FINE_PX           = 90.0   # X축 미세 조정 픽셀

# 수동 조그의 홀드/탭 동작을 결정하는 값입니다.
MANUAL_JOG_HOLD_MS             = 120
# R축 탭 이동 각도입니다.
# 수동 R 탭과 자동 얼라인의 미세 펄스 보정이 이 값을 함께 사용합니다.
R_JOG_TAP_DEG                  = 0.35


# 설정된 기구 상수로 1mm 이동에 필요한 스텝 수를 계산합니다.
def linear_steps_per_mm():
    steps_per_rev = (360.0 / LINEAR_MOTOR_STEP_ANGLE_DEG) * LINEAR_MICROSTEPS * LINEAR_GEAR_RATIO
    mm_per_rev = LINEAR_PULLEY_TEETH * LINEAR_BELT_PITCH_MM
    if mm_per_rev <= 0:
        return 0.0
    return steps_per_rev / mm_per_rev


# 스텝 수를 mm로 바꿔 UI에 표시할 때 사용하는 보조 함수입니다.
def linear_steps_to_mm(steps):
    spmm = linear_steps_per_mm()
    if spmm <= 0:
        return 0.0
    return float(steps) / spmm
