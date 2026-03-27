# SPINS 통합 HMI 문서

## 1. 프로젝트 개요

이 프로젝트는 SPINS 장비용 통합 HMI(Human-Machine Interface)입니다.  
현재 기준으로 하나의 메인 프로그램 안에서 아래 공정을 순차 또는 수동 진입 방식으로 다룹니다.

- Align / Expose
- Inspect
- ET-Test
- Sort 준비 상태

코드는 기존 단일 대형 파일 구조에서 벗어나, `PyQt6 + 모듈 분리 + 공통 메인 윈도우` 구조로 정리되어 있습니다.  
즉, 각 공정 화면은 분리된 모듈로 유지하고, 실제 실행과 상태 전환은 메인 윈도우에서 통합 제어하는 방식입니다.

이 문서는 현재 소스 기준의 구조와 책임 분리를 설명합니다.  
다른 담당자가 UI, 비전, 모터 제어, 펌웨어를 이어서 수정할 수 있도록 작성했습니다.

---

## 1.1 저장소 포함/제외 정책

현재 Git 저장소는 `재현 가능한 코드 저장소`를 목표로 합니다.

저장소에 포함하는 항목:

- Qt6 HMI 코드
- Arduino 펌웨어
- 실행/설치 문서
- 학습 스크립트

저장소에서 제외하는 항목:

- 가상환경 `venv/`
- Python 캐시 `__pycache__/`
- 학습 결과 `runs/`
- 다운로드된 데이터셋 `Cross_Alignment_Project-1/`
- 기본 가중치 파일 `*.pt`

즉, 코드와 문서는 저장소에 남기고, 다운로드/생성 가능한 대용량 자산은 저장소 밖에서 관리하는 정책입니다.

---

## 2. 현재 기술 스택

- Python 3.12
- PyQt6
- OpenCV (`cv2`)
- Ultralytics YOLO
- Supervision
- pyserial
- Arduino + TB6600 기반 모터 제어

---

## 3. 실행 진입점

실제 기준 실행 파일은 아래입니다.

- [main_ui.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\main_ui.py)

호환용 래퍼는 아래입니다.

- [spins_master_ui_qt6.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_master_ui_qt6.py)

실행 예시:

```powershell
python main_ui.py
```

원클릭 실행 배치파일:

- [run_spins_hmi.bat](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\run_spins_hmi.bat)

이 배치파일은 실행 기능만 담당합니다.

1. 프로젝트 폴더 기준으로 `venv\Scripts\python.exe`가 있는지 확인
2. 있으면 `main_ui.py` 실행
3. 없으면 에러를 출력하고 종료

즉, 이 배치파일은 `가상환경 생성`이나 `패키지 설치`를 하지 않습니다.  
먼저 `venv`와 패키지 설치를 완료한 뒤, 그 다음부터 폴더 안에서 `run_spins_hmi.bat` 더블클릭으로 실행하는 용도입니다.

---

## 3.1 최초 환경 준비 순서

다른 PC에서 처음 세팅할 때는 아래 순서를 권장합니다.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

학습까지 같이 사용할 경우:

```powershell
pip install -r requirements-train.txt
```

그 다음부터는 아래 중 하나로 실행하면 됩니다.

```powershell
python main_ui.py
```

또는

```powershell
run_spins_hmi.bat
```

---

## 4. 루트 폴더 구조

현재 루트 기준 주요 항목은 다음과 같습니다.

- [main_ui.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\main_ui.py)
  - Qt6 통합 HMI 실행 진입점
- [spins_ui](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui)
  - 실제 통합 UI 코드 패키지
- [arduino_tb6600](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\arduino_tb6600)
  - Arduino 펌웨어
- [train.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\train.py)
  - 모델 학습 스크립트
- [runs](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\runs)
  - 모델 결과 및 가중치 저장 폴더
- [Cross_Alignment_Project-1](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\Cross_Alignment_Project-1)
  - 정렬 데이터셋
- [requirements.txt](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\requirements.txt)
  - UI 실행용 기본 의존성
- [requirements-train.txt](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\requirements-train.txt)
  - 학습/데이터셋 작업용 추가 의존성
- [run_spins_hmi.bat](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\run_spins_hmi.bat)
  - 원클릭 실행 배치파일

주의:

- `venv/`, `runs/`, `Cross_Alignment_Project-1/`, `arduino_tb6600/`는 유지 대상입니다.
- 이전 Qt5 통합 UI 대형 파일은 제거했고, 현재는 Qt6 구조가 기준입니다.

---

## 5. `spins_ui` 패키지 구조

### 5.1 메인 통합 계층

- [spins_ui/main_window.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\main_window.py)
  - 전체 메인 윈도우
  - 페이지 조립
  - 상태 전환
  - 카메라 스레드 시작/정지
  - 시리얼 응답 처리
  - 자동 얼라인 루프
  - 노광, 검사, ET-Test 흐름 제어

- [spins_ui/core.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\core.py)
  - `ProcessState`
  - `StateManager`
  - `SerialManager`
  - `CameraThread`
  - YOLO 기반 얼라인 비전 처리
  - 카메라 fallback 처리

- [spins_ui/config.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\config.py)
  - 카메라 인덱스
  - 모델 경로
  - 정렬 판정값
  - R축 펄스 각도
  - X/Y 기구 계산값
  - 축 사용 여부
  - 홈 생략 여부

- [spins_ui/components.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\components.py)
  - 상단 시리얼 바
  - 공정 단계 바
  - 디버그 로그 패널
  - 공통 안전 패널
  - 공통 웨이퍼 맵 위젯

- [spins_ui/styles.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\styles.py)
  - 전체 공통 QSS 스타일

### 5.2 페이지 모듈

- [spins_ui/pages/align_page.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\pages\align_page.py)
  - Align / Expose 화면 전용 UI
- [spins_ui/pages/inspect_page.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\pages\inspect_page.py)
  - Inspect 화면 전용 UI
- [spins_ui/pages/et_test_page.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\pages\et_test_page.py)
  - ET-Test 화면 전용 UI

---

## 6. 메인 윈도우 구조

[spins_ui/main_window.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\main_window.py)의 메인 화면은 아래 구조를 기준으로 합니다.

### 상단

- 시리얼 연결 바
  - 포트 선택
  - Refresh
  - Connect / Disconnect
  - Settings
  - 연결 상태 LED

- 공정 단계 바
  - Idle
  - Align
  - Expose
  - Move
  - Inspect
  - Sort

### 본문 3열

- 현재 메인 3열은 `QSplitter` 기반입니다.
- 좌/중/우 경계를 사용자가 직접 드래그해 폭을 조절할 수 있습니다.
- 조절한 비율은 다음 실행 시 복원되도록 저장됩니다.

- 좌측 열
  - 현재 공정용 좌측 제어 패널
  - Debug Log

- 중앙 열
  - 현재 공정의 메인 카메라 또는 메인 화면

- 우측 열
  - 현재 공정용 우측 정보 패널
  - 공통 `System Control`

### 하단 상태

- `QStatusBar`에
  - 연결 포트
  - 현재 상태
  - X 오차
  - 각도 오차
  표시

---

## 7. 공정별 UI 구조

## 7.1 Align / Expose

[spins_ui/pages/align_page.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\pages\align_page.py)

### 좌측 패널

- `Linear Stage`
  - `Linear Home`
  - 홈 상태 표시

- `Jog Control`
  - X / Y 현재 위치 카드
  - `X+ / X-`
  - `Y+ / Y-`
  - `R+ / R-`

- `Speed Control`
  - `XY Jog Speed`
  - `R Jog Speed`

- `Manual Align`
  - 수동 얼라인 시작 버튼

중요:

- 좌측 패널은 현재 `QScrollArea` 기반 적응형 구조입니다.
- 창 높이가 부족하면 패널 내부 스크롤로 내용을 살립니다.
- 디버그창이 너무 커서 위 내용을 밀지 않도록, 메인 윈도우 쪽에서 디버그 영역 높이를 제한합니다.

### 중앙 패널

- Align / Expose 제목
- 카메라 영상
- 중앙 레티클 오버레이
- 카메라 인덱스 표시

### 우측 패널

- `Vision Result`
  - Angle
  - Status
  - Keys
  - Wafer

- `Exposure`
  - `Auto After Align`
  - 진행률 바

---

## 7.2 Inspect

[spins_ui/pages/inspect_page.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\pages\inspect_page.py)

현재는 검사 공정 골격 중심입니다.

- 중앙: 검사 카메라
- 좌측: 마지막 검사 이미지 또는 보조 패널
- 우측: PASS / FAIL / Yield 정보

현재 실제 AI 검사 판정은 완전 연동 상태가 아니며, 화면 구조와 수동 판정 흐름이 우선 구성되어 있습니다.

---

## 7.3 ET-Test

[spins_ui/pages/et_test_page.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\pages\et_test_page.py)

현재 ET-Test는 다음 구조입니다.

- 중앙: ET-Test 카메라
- 좌측: 테스트 실행 / 완료 / 초기화
- 우측: 수율 정보 + 웨이퍼 맵

[spins_ui/components.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\components.py)의 `WaferMapWidget`은 참고 이미지 느낌의 타일형 웨이퍼를 그립니다.

색상 의미:

- 연한 파란색: 정상
- 연한 붉은색: 불량
- 회색: 미측정

현재 ET-Test는 실제 계측 데이터 대신 UI 골격과 시뮬레이션 출력 중심입니다.

---

## 8. 공정 상태 머신

[spins_ui/core.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\core.py)와 [spins_ui/main_window.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\main_window.py)에서 상태 머신을 다룹니다.

사용 상태:

- `IDLE`
- `ALIGNING`
- `EXPOSING`
- `MOVING`
- `INSPECTING`
- `ET_TEST`
- `SORTING`

특징:

- 상단 단계 바를 클릭해 수동 진입 가능
- 자동 공정 실행 중에는 임의 전환 제한
- 상태가 바뀌면 좌/중/우 스택이 함께 바뀜

---

## 9. 카메라 구조

[spins_ui/core.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\core.py)의 `CameraThread`가 각 카메라를 담당합니다.

현재 정책:

- Aligner 카메라와 Inspector 카메라는 독립 스레드
- `camera 1`이 열리지 않으면 자동으로 `camera 0` fallback
- 둘 다 실패하면 `camera_not found` 상태 표시

설정 위치:

- [spins_ui/config.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\config.py)
  - `ALIGNER_CAMERA_INDEX`
  - `INSPECTOR_CAMERA_INDEX`

---

## 10. 얼라인 비전 로직

### 10.1 검출 기준

[spins_ui/core.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\core.py)에서 YOLO OBB 결과를 사용합니다.

주요 추출 대상:

- Wafer 중심
- Key 2개 중심

### 10.2 현재 R 정렬 기준

최근 구조에서 R 정렬은 단순히 Key 2개의 선 기울기만 쓰지 않고,  
`Key 중점이 Wafer 중심 기준 위쪽에서 얼마나 벗어났는지`를 각도로 계산합니다.

즉:

- 목표: Key 중점이 웨이퍼 중심 기준 위쪽 방향
- 양수: CCW 쪽으로 보정
- 음수: CW 쪽으로 보정

이 방식은 아래쪽 정렬이나 180도 모호성 문제를 줄이기 위한 것입니다.

### 10.3 상태 문구

비전 결과는 다음 상태를 씁니다.

- `ALIGNED`
- `ROTATE CCW`
- `ROTATE CW`
- `UPSIDE DOWN`
- `Searching for 2nd key`
- `Too many keys`
- `No align key detected`

---

## 11. 자동 얼라인 구조

[spins_ui/main_window.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\main_window.py)

현재 자동 얼라인 순서는 다음과 같습니다.

1. `X` 정렬
2. `R` 정렬
3. 정렬 완료 시 노광 단계 진입

### 11.1 X 정렬

현재 테스트 기준:

- X + R 구조 우선
- X가 먼저 중심 수직선에 들어와야 R로 넘어감

X 정렬 완료 기준:

- `AUTO_ALIGN_X_TARGET_PX`
- `AUTO_ALIGN_X_STABLE_FRAMES`

### 11.2 R 정렬

현재 R 정렬은 세 단계로 나뉩니다.

- 연속 회전 정렬
- 10도 이하 감속 구간
- 0도 통과 후 `zero-lock` 미세 보정

특징:

- 방향은 현재 프레임 오차(raw) 우선
- 정지 판정도 raw 오차 기준
- 0도 통과 후에는 연속 회전 대신 고정 각도 펄스 보정
- 1도 이내로 들어오면 정렬 완료 처리

---

## 12. 수동 얼라인 / 수동 조그 구조

### 12.1 Manual Align

`Manual Align` 버튼은 자동 얼라인과 같은 루프를 사용합니다.

즉:

- 별도 계산이 아니라
- 현재 비전값을 읽고
- `X -> R` 순서의 자동 루프를 수동 시작하는 구조입니다.

### 12.2 수동 R 탭과 자동 미세 보정 공유

현재 `R`축의 짧은 탭 이동 각도는 [spins_ui/config.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\config.py)의 아래 값이 기준입니다.

```python
R_JOG_TAP_DEG = 0.35
```

이 값은 현재 다음 동작이 공유합니다.

- 수동 `R` 탭
- 자동 얼라인 `Fine approach`
- 자동 얼라인 `Zero-lock`

즉, `툭 한 번 움직이는 각도`를 바꾸고 싶으면 지금은 `R_JOG_TAP_DEG` 하나만 조정하면 됩니다.

---

## 13. 정렬 튜닝에 중요한 설정값

[spins_ui/config.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\config.py)

### R 정렬 관련

- `ALIGN_TOLERANCE_DEG`
  - 정렬 완료 판단 기준 각도
- `AUTO_ALIGN_TARGET_DEG`
  - 자동 보정 목표 각도
- `AUTO_ALIGN_RELEASE_DEG`
  - 연속 회전에서 정지 판단을 시작하는 각도
- `AUTO_ALIGN_CREEP_THRESHOLD_DEG`
  - creep 계열 미세 보정 구간
- `AUTO_ALIGN_SLOWDOWN_DEG`
  - 이 각도 이하면 속도 절반 감속
- `AUTO_ALIGN_ZERO_LOCK_DEG`
  - 0도 통과 이후 최종 정렬 완료 구간
- `ANGLE_SMOOTHING_ALPHA`
  - 프레임 간 각도 평활화 강도
- `R_JOG_TAP_DEG`
  - 수동/자동 미세 탭 각도

### X 정렬 관련

- `AUTO_ALIGN_X_TARGET_PX`
- `AUTO_ALIGN_X_RELEASE_PX`
- `AUTO_ALIGN_X_STABLE_FRAMES`
- `AUTO_ALIGN_X_FINE_PX`

### 조그 관련

- `MANUAL_JOG_HOLD_MS`
  - 길게 누를 때 연속 조그로 전환되는 시간

---

## 14. 카메라 / 설치 보정 관련 설정값

[spins_ui/config.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\config.py)

- `ALIGN_CAMERA_OFFSET_DEG`
  - 카메라 설치 오차 보정
- `ALIGN_ROTATION_SIGN`
  - 현재 카메라/장비 좌표계의 회전 부호 보정

주의:

- 이 값이 잘못되면 가까운 쪽이 아니라 먼 쪽으로 회전할 수 있습니다.
- 최근 수정에서 이 부호값이 실제 장비 기준으로 중요해졌습니다.

---

## 15. 축 사용 / 홈 생략 설정

현재는 X + R 테스트를 자주 하기 때문에, 특정 축만 켜고 특정 축 홈을 생략할 수 있게 되어 있습니다.

[spins_ui/config.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\config.py)

관련 값:

- `ENABLE_X_STAGE`
- `ENABLE_Y_STAGE`
- `ENABLE_R_STAGE`
- `REQUIRE_LINEAR_HOME_FOR_PROCESS`
- `SKIP_X_HOME`
- `SKIP_Y_HOME`

예:

```python
ENABLE_X_STAGE = True
ENABLE_Y_STAGE = False
ENABLE_R_STAGE = True

SKIP_X_HOME = False
SKIP_Y_HOME = True
```

---

## 16. X/Y 이동량 표시 구조

X/Y는 UI와 Arduino가 같은 기구 상수를 기준으로 `steps/mm`를 계산해야 합니다.

### Python 쪽

[spins_ui/config.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\config.py)

- `LINEAR_MOTOR_STEP_ANGLE_DEG`
- `LINEAR_MICROSTEPS`
- `LINEAR_GEAR_RATIO`
- `LINEAR_PULLEY_TEETH`
- `LINEAR_BELT_PITCH_MM`

### Arduino 쪽

[arduino_tb6600.ino](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\arduino_tb6600\arduino_tb6600.ino)

- `linearMotorStepAngleDeg`
- `linearMicrosteps`
- `linearGearRatio`
- `linearPulleyTeeth`
- `linearBeltPitchMm`

중요:

- 두 파일의 값이 같아야 UI의 mm 표시와 실제 이동량이 일치합니다.

---

## 17. 시리얼 / Arduino 프로토콜 구조

[spins_ui/core.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\core.py)의 `SerialManager`와  
[arduino_tb6600.ino](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\arduino_tb6600\arduino_tb6600.ino)가 연결됩니다.

주요 명령 예시:

- `ALIGN:<deg>:<speed>`
- `JOG_START_CW:<speed>`
- `JOG_START_CCW:<speed>`
- `JOG_START_X_POS:<speed>`
- `JOG_START_X_NEG:<speed>`
- `JOG_START_Y_POS:<speed>`
- `JOG_START_Y_NEG:<speed>`
- `JOG_STOP`
- `HOME_LINEAR`
- `HOME_LINEAR:<skipX>:<skipY>`
- `EMERGENCY_STOP`
- `RESET_ESTOP`

주요 응답 예시:

- `DONE`
- `ABORTED`
- `ESTOP_RESET`
- `EMERGENCY_STOPPED`
- `LINEAR_HOME_STARTED`
- `LINEAR_HOME_DONE`
- `JOG_STOPPED`
- `POS:X:<steps>:Y:<steps>`
- `ERROR:ESTOP_ACTIVE`
- `ERROR:HOME_REQUIRED`
- `ERROR:X_DISABLED`
- `ERROR:Y_DISABLED`
- `ERROR:R_DISABLED`

---

## 18. Arduino 펌웨어 역할

[arduino_tb6600/arduino_tb6600.ino](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\arduino_tb6600\arduino_tb6600.ino)

역할:

- R축 회전
- X/Y 연속 조그
- X/Y 홈
- 소프트 리밋
- E-Stop 반영
- UI에 현재 위치(step) 전송

현재 펌웨어에서 중요한 특징:

- `rJogChunkSteps`
  - R 연속 회전 응답성에 영향
- `speedToDelay()`
  - UI 속도값을 실제 스텝 지연으로 변환
- 홈 완료 후 `POS:X:Y` 전송
- 홈 생략 플래그 처리 가능

주의:

- `.ino`를 수정하면 반드시 다시 업로드해야 합니다.
- Python만 수정하고 펌웨어를 안 올리면 실제 장비 체감이 다를 수 있습니다.

---

## 19.1 학습 스크립트와 API 키

[train.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\train.py)는 Roboflow API 키를 코드에 직접 저장하지 않습니다.  
학습 전 환경변수로 API 키를 넣어야 합니다.

PowerShell 예시:

```powershell
$env:ROBOFLOW_API_KEY="<your_key>"
python train.py
```

특징:

- API 키가 없으면 학습을 시작하지 않고 명확한 안내 문구로 종료합니다.
- 다운로드된 데이터셋 폴더에 `data.yaml`이 없으면 자동 생성합니다.
- 데이터셋과 가중치 파일은 저장소에 포함하지 않는 전제입니다.

---

## 19. 공통 안전 패널

[spins_ui/components.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\components.py)의 `SafetyPanel`

모든 공정에서 우측 하단 고정 위치를 유지합니다.

구성:

- 상태 박스
- `EMERGENCY STOP`
- `Start`
- `Stop`
- `Restart`

특징:

- 공정 화면이 바뀌어도 위치 고정
- UI/시리얼 상태에 따라 버튼 활성/비활성 갱신
- 최근 레이아웃 수정으로 우측 패널이 더 큼직하게 보이도록 조정됨

---

## 20. 현재 UI 적응형 구조 메모

최근 레이아웃 수정 포인트는 다음과 같습니다.

### 좌측 열

- 제어패널이 우선, 디버그는 아래에서 작게 유지
- 좌측 Align 제어패널은 스크롤 가능한 적응형 구조
- `Speed Control`과 `Manual Align`은 한 줄에 나란히 배치
- 좌측 열 전체 폭은 메인 스플리터에서 사용자가 직접 조절 가능

### 우측 열

- `Exposure`와 `System Control`을 더 크게
- 패널 말단의 stretch 공백을 줄임
- 위젯 자체를 키우고 간격은 좁히는 방향으로 조정
- 우측 열 전체 폭도 메인 스플리터에서 직접 조절 가능

즉, 현재 UI 철학은:

- 화면이 작아져도 겹치지 않기
- 필요한 버튼은 가능한 한 항상 보이기
- 빈 공간보다 실제 제어 패널을 더 크게 보이게 하기
- 사용자가 장비 상황에 맞게 좌/중/우 비율을 직접 조정할 수 있게 하기

---

## 21. 태블릿 운용 계획

현재 기준 태블릿 대응은 별도 웹 UI나 별도 앱이 아니라,  
메인 PC에서 실행 중인 Qt 화면을 태블릿으로 `원격 미러링`하는 방향을 기본으로 잡고 있습니다.

권장 방식:

- 메인 PC에서 [main_ui.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\main_ui.py) 또는 [run_spins_hmi.bat](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\run_spins_hmi.bat)로 HMI 실행
- 태블릿에서는 원격 데스크톱 / 원격 제어 앱으로 같은 화면에 접속

장점:

- 기존 Qt UI, 버튼 로직, 시리얼 로직, 비전 로직을 그대로 재사용 가능
- 데스크탑과 태블릿의 동작 기준이 분리되지 않음
- 유지보수 포인트가 늘어나지 않음

한계:

- 네트워크 지연에 따라 터치 반응이 늦어질 수 있음
- 비상정지는 여전히 장비 측 물리 인터락이 우선이어야 함
- 태블릿 전용 레이아웃이나 큰 버튼 최적화는 아직 별도 구현되지 않음

향후 확장 포인트:

- 현재 버튼 입력을 공통 action 계층으로 한 번 더 추상화하면
- 나중에 태블릿 전용 큰 버튼 화면이나 간소화 레이아웃을 추가하기 쉬움
- 즉, 현재는 동일 화면 미러링을 사용하고 추후 필요 시 전용 태블릿 레이아웃을 얹는 순서가 적합함

---

## 22. 현재 알려진 한계

- X/Y 실제 장비 연동은 진행 중이며 테스트 조건에 따라 비활성화해서 사용 중
- Inspect는 아직 완전한 AI 판별 공정이 아님
- ET-Test는 실제 측정 장비 연동 전 UI 골격 중심
- Sort 공정은 상태 단계 수준이며 전용 액추에이터 로직은 미완성

---

## 23. 코드 수정 시 권장 진입점

다른 파트 담당자가 수정할 때는 보통 아래 순서로 접근하면 빠릅니다.

### UI 배치 수정

- [spins_ui/pages/align_page.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\pages\align_page.py)
- [spins_ui/pages/inspect_page.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\pages\inspect_page.py)
- [spins_ui/pages/et_test_page.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\pages\et_test_page.py)
- [spins_ui/components.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\components.py)

### 공정 흐름 / 자동 정렬 수정

- [spins_ui/main_window.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\main_window.py)
- [spins_ui/config.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\config.py)

### 비전 로직 수정

- [spins_ui/core.py](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\spins_ui\core.py)

### 모터 응답 / 실제 구동 감각 수정

- [arduino_tb6600/arduino_tb6600.ino](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\arduino_tb6600\arduino_tb6600.ino)

---

## 24. 실행 및 검증

실행:

```powershell
python main_ui.py
```

원클릭 실행:

```powershell
run_spins_hmi.bat
```

주의:

- [run_spins_hmi.bat](C:\Users\pbjc0\OneDrive\바탕 화면\Wafer_camera\run_spins_hmi.bat)은 현재 실행 전용입니다.
- `venv`가 없으면 자동 설치를 하지 않고 종료합니다.
- 따라서 최초 1회는 직접 가상환경과 패키지를 준비해야 합니다.

### 권장 설치 방식

다른 PC에서 UI만 실행할 경우:

```powershell
pip install -r requirements.txt
```

학습까지 같이 사용할 경우:

```powershell
pip install -r requirements-train.txt
```

설치 파일 구성 의도:

- `requirements.txt`
  - 실제 통합 HMI 실행에 필요한 최소 의존성 위주
- `requirements-train.txt`
  - `train.py`까지 고려한 추가 의존성 포함

즉, 실행 담당자는 가볍게 설치하고, 학습 담당자만 추가 패키지를 설치하도록 나눴습니다.

최근 파이썬 문법 검증은 보통 아래 방식으로 확인합니다.

```powershell
python -m py_compile main_ui.py spins_ui\main_window.py spins_ui\core.py spins_ui\components.py spins_ui\pages\align_page.py spins_ui\pages\inspect_page.py spins_ui\pages\et_test_page.py
```

주의:

- Python 문법 통과와 실제 장비 동작은 별개입니다.
- 모터 관련 수정은 Arduino 업로드까지 해야 실제 반영됩니다.

---

## 25. 다음 담당자가 보면 좋은 핵심 포인트

짧게 요약하면 현재 구조는 다음과 같습니다.

- 실행 진입점은 `main_ui.py`
- 실제 로직은 `spins_ui` 패키지 안에 분리
- 공정 화면은 `pages/` 아래에서 분리
- 상태 전환과 자동 얼라인은 `main_window.py`
- 비전 추론과 시리얼은 `core.py`
- 튜닝 숫자는 `config.py`
- 실제 모터 응답은 `.ino`

즉,  
`UI 모양`은 페이지 파일에서,  
`공정 흐름`은 메인 윈도우에서,  
`비전 계산`은 코어에서,  
`물리 구동 감각`은 Arduino에서 만지면 됩니다.
