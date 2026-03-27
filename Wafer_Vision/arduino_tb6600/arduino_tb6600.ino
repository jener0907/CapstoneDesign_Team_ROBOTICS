// ==============================================================
// SPINS - R 회전축 + XY 리니어 스테이지 통합 제어 펌웨어
//
// 지원 커맨드 예시
//   ALIGN:1.5:20.0
//   JOG_START_CW:15.0
//   JOG_START_CCW:15.0
//   JOG_START_X_POS:30.0
//   JOG_START_X_NEG:30.0
//   JOG_START_Y_POS:30.0
//   JOG_START_Y_NEG:30.0
//   JOG_STOP
//   HOME_LINEAR
//   EMERGENCY_STOP
//   RESET_ESTOP
//
// 주의
//   아래 핀 번호, 방향 레벨, steps/mm 값은 실제 배선과 기구 사양에 맞춰 반드시 조정해야 합니다.
// ==============================================================

// ========= [사용자 설정 영역: 하드웨어에 맞게 조정하세요] =========

// R축(TB6600) 핀 설정
const int rDirPin  = 2;
const int rStepPin = 3;

// X/Y축(리니어 스테이지) 핀 설정
const int xDirPin  = 4;
const int xStepPin = 5;
const int yDirPin  = 6;
const int yStepPin = 7;

// X/Y 홈 리밋 센서 핀 설정
const int xHomePin = 8;
const int yHomePin = 9;

// 홈 센서 입력 방식
// 대부분은 INPUT_PULLUP + 스위치 눌리면 LOW 구조를 사용합니다.
const int homeTriggerState = LOW;

// 방향 핀 레벨 정의
// HIGH/LOW 중 어떤 값이 +방향인지 실제 배선과 기구 방향에 맞춰 조정하세요.
const int rCwDirLevel       = HIGH;
const int rCcwDirLevel      = LOW;
const int xPositiveDirLevel = HIGH;
const int xNegativeDirLevel = LOW;
const int yPositiveDirLevel = HIGH;
const int yNegativeDirLevel = LOW;

// 홈으로 접근할 때 사용할 방향 레벨
const int xHomeDirLevel = xNegativeDirLevel;
const int yHomeDirLevel = yNegativeDirLevel;

// R축 모터 및 기어비 설정
const float motorStepAngle = 1.8;
const int   microsteps     = 16;
const float gearRatio      = 1.0;

// X/Y축 이동량 설정
// 아래 값만 실제 하드웨어에 맞게 수정하면 xStepsPerMm, yStepsPerMm는 자동 계산됩니다.
// 예시:
//   1.8도 스텝모터, 마이크로스텝 16, GT2 20T 풀리, 감속 없음 -> 80 steps/mm
//   1.8도 스텝모터, 마이크로스텝 4,  GT2 20T 풀리, 감속 없음 -> 20 steps/mm
// 중요:
// spins_ui/config.py의 LINEAR_MOTOR_STEP_ANGLE_DEG, LINEAR_MICROSTEPS,
// LINEAR_GEAR_RATIO, LINEAR_PULLEY_TEETH, LINEAR_BELT_PITCH_MM와 같아야
// UI에 표시되는 mm 값과 실제 아두이노 내부 계산이 일치합니다.
// 현재 장비에서 풀리/벨트/기어비가 그대로라면, 실질적으로는 양쪽
// "마이크로스텝" 값만 같이 바꿔도 mm 오차를 맞출 수 있습니다.
// 현재 기본값은 X + R 얼라인 테스트 기준입니다.
// Y축까지 연결한 뒤에는 enableYAxis를 true로 바꾸면 됩니다.
const bool enableXAxis        = true;
const bool enableYAxis        = false;
const bool enableRAxis        = true;
const float linearMotorStepAngleDeg = 1.8;
const int linearMicrosteps    = 16;
const float linearGearRatio   = 1.0;
const float linearPulleyTeeth = 20.0;
const float linearBeltPitchMm = 2.0;
const float xTravelMm         = 300.0;
const float yTravelMm         = 300.0;

// 속도 설정
const int defaultStepDelayMicroseconds    = 300;
const int minStepDelayMicroseconds        = 60;
// 정렬용 저속 회전을 더 세밀하게 만들기 위해 상한 지연을 넉넉히 둡니다.
const int maxStepDelayMicroseconds        = 2400;
const int linearHomeFastDelayMicroseconds = 1000; // 호밍 고속
const int linearHomeSlowDelayMicroseconds = 2200; // 호밍 저속
const float linearHomeBackoffMm           = 3.0;

// 연속 조그는 loop()가 반복될 때마다 아래 청크만큼 펄스를 추가로 발행합니다.
// R축 청크가 너무 크면 UI가 감속/정지 명령을 보내도 다음 반영이 늦어져 목표를 지나치기 쉽습니다.
const long rJogChunkSteps = 40;
const long linearJogChunkSteps = 320;

// 홈 탐색 최대 시간(ms). 센서 이상 시 무한 루프를 막기 위한 값입니다.
const unsigned long homeSearchTimeoutMs = 20000UL;

// ============================================================== 

// R축 관련 계산값
float rStepsPerDegree = 0.0;

// XY축 소프트 리밋 계산값
float xStepsPerMm = 0.0;
float yStepsPerMm = 0.0;
long xTravelSteps = 0;
long yTravelSteps = 0;

// 현재 상태 변수
bool emergencyStopActive = false;
bool jogActive = false;
bool linearStageHomed = false;
bool xAxisHomed = false;
bool yAxisHomed = false;
int currentStepDelayMicroseconds = defaultStepDelayMicroseconds;

// XY는 홈 이후 현재 스텝 위치를 절대좌표처럼 추적합니다.
long xPositionSteps = 0;
long yPositionSteps = 0;

enum JogAxis {
  JOG_AXIS_NONE,
  JOG_AXIS_R,
  JOG_AXIS_X,
  JOG_AXIS_Y
};

JogAxis activeJogAxis = JOG_AXIS_NONE;
int activeJogDirection = 0; // +1 또는 -1

void emitLinearPosition();
float computeLinearStepsPerMm();

void setup() {
  Serial.begin(9600);

  pinMode(rDirPin, OUTPUT);
  pinMode(rStepPin, OUTPUT);
  pinMode(xDirPin, OUTPUT);
  pinMode(xStepPin, OUTPUT);
  pinMode(yDirPin, OUTPUT);
  pinMode(yStepPin, OUTPUT);

  pinMode(xHomePin, INPUT_PULLUP);
  pinMode(yHomePin, INPUT_PULLUP);

  digitalWrite(rDirPin, LOW);
  digitalWrite(rStepPin, LOW);
  digitalWrite(xDirPin, LOW);
  digitalWrite(xStepPin, LOW);
  digitalWrite(yDirPin, LOW);
  digitalWrite(yStepPin, LOW);

  rStepsPerDegree = ((360.0 / motorStepAngle) * microsteps * gearRatio) / 360.0;
  xStepsPerMm = computeLinearStepsPerMm();
  yStepsPerMm = computeLinearStepsPerMm();
  xTravelSteps = lround(xTravelMm * xStepsPerMm);
  yTravelSteps = lround(yTravelMm * yStepsPerMm);

  Serial.println("SPINS Motion Controller Initialized.");
  Serial.print("R steps/deg: ");
  Serial.println(rStepsPerDegree);
  Serial.print("X travel steps: ");
  Serial.println(xTravelSteps);
  Serial.print("Y travel steps: ");
  Serial.println(yTravelSteps);
  Serial.print("Linear steps/mm: ");
  Serial.println(xStepsPerMm);
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    handleCommand(command);
  }

  if (jogActive && !emergencyStopActive) {
    runJogChunk();
  }
}

// 상위 UI가 보낸 문자열 명령을 해석합니다.
void handleCommand(String command) {
  if (command == "EMERGENCY_STOP") {
    emergencyStopActive = true;
    jogActive = false;
    activeJogAxis = JOG_AXIS_NONE;
    Serial.println("EMERGENCY_STOPPED");
    return;
  }

  if (command == "RESET_ESTOP") {
    emergencyStopActive = false;
    jogActive = false;
    activeJogAxis = JOG_AXIS_NONE;
    Serial.println("ESTOP_RESET");
    return;
  }

  if (emergencyStopActive) {
    Serial.println("ERROR:ESTOP_ACTIVE");
    return;
  }

  if (command == "HOME_LINEAR") {
    if (!enableXAxis && !enableYAxis) {
      linearStageHomed = true;
      Serial.println("LINEAR_HOME_DONE");
      return;
    }
    homeLinearStage(false, false);
    return;
  }

  if (command.startsWith("HOME_LINEAR:")) {
    bool skipXHome = parseFirstFloat(command, 12) > 0.5;
    bool skipYHome = parseSecondFloat(command, 12, 0.0) > 0.5;
    homeLinearStage(skipXHome, skipYHome);
    return;
  }

  if (command.startsWith("ALIGN:")) {
    if (!enableRAxis) {
      Serial.println("ERROR:R_DISABLED");
      return;
    }
    float targetAngle = parseFirstFloat(command, 6);
    float speedValue = parseSecondFloat(command, 6, 0.0);
    int stepDelay = speedToDelay(speedValue);
    rotateDegrees(targetAngle, stepDelay);
    if (!emergencyStopActive) {
      Serial.println("DONE");
    }
    return;
  }

  if (command == "MOVE_CW") {
    if (!enableRAxis) {
      Serial.println("ERROR:R_DISABLED");
      return;
    }
    rotateDegrees(1.0, currentStepDelayMicroseconds);
    return;
  }

  if (command == "MOVE_CCW") {
    if (!enableRAxis) {
      Serial.println("ERROR:R_DISABLED");
      return;
    }
    rotateDegrees(-1.0, currentStepDelayMicroseconds);
    return;
  }

  if (command.startsWith("JOG_START_CW")) {
    if (!enableRAxis) {
      Serial.println("ERROR:R_DISABLED");
      return;
    }
    currentStepDelayMicroseconds = speedToDelay(parseTrailingFloat(command, 12));
    startJog(JOG_AXIS_R, 1);
    Serial.println("JOGGING_CW");
    return;
  }

  if (command.startsWith("JOG_START_CCW")) {
    if (!enableRAxis) {
      Serial.println("ERROR:R_DISABLED");
      return;
    }
    currentStepDelayMicroseconds = speedToDelay(parseTrailingFloat(command, 13));
    startJog(JOG_AXIS_R, -1);
    Serial.println("JOGGING_CCW");
    return;
  }

  if (command.startsWith("JOG_START_X_POS")) {
    if (!enableXAxis) {
      Serial.println("ERROR:X_DISABLED");
      return;
    }
    currentStepDelayMicroseconds = speedToDelay(parseTrailingFloat(command, 15));
    startJog(JOG_AXIS_X, 1);
    Serial.println("JOGGING_X_POS");
    return;
  }

  if (command.startsWith("JOG_START_X_NEG")) {
    if (!enableXAxis) {
      Serial.println("ERROR:X_DISABLED");
      return;
    }
    currentStepDelayMicroseconds = speedToDelay(parseTrailingFloat(command, 15));
    startJog(JOG_AXIS_X, -1);
    Serial.println("JOGGING_X_NEG");
    return;
  }

  if (command.startsWith("JOG_START_Y_POS")) {
    if (!enableYAxis) {
      Serial.println("ERROR:Y_DISABLED");
      return;
    }
    currentStepDelayMicroseconds = speedToDelay(parseTrailingFloat(command, 15));
    startJog(JOG_AXIS_Y, 1);
    Serial.println("JOGGING_Y_POS");
    return;
  }

  if (command.startsWith("JOG_START_Y_NEG")) {
    if (!enableYAxis) {
      Serial.println("ERROR:Y_DISABLED");
      return;
    }
    currentStepDelayMicroseconds = speedToDelay(parseTrailingFloat(command, 15));
    startJog(JOG_AXIS_Y, -1);
    Serial.println("JOGGING_Y_NEG");
    return;
  }

  if (command == "JOG_STOP") {
    jogActive = false;
    activeJogAxis = JOG_AXIS_NONE;
    emitLinearPosition();
    Serial.println("JOG_STOPPED");
  }
}

// 연속 조그의 현재 축에 맞춰 일정량의 펄스를 발행합니다.
void runJogChunk() {
  if (activeJogAxis == JOG_AXIS_R) {
    int dirLevel = activeJogDirection > 0 ? rCwDirLevel : rCcwDirLevel;
    digitalWrite(rDirPin, dirLevel);
    for (long i = 0; i < rJogChunkSteps; i++) {
      if (!keepMotionAlive()) {
        return;
      }
      pulseStepPin(rStepPin, currentStepDelayMicroseconds);
    }
    return;
  }

  if (activeJogAxis == JOG_AXIS_X) {
    int dirLevel = activeJogDirection > 0 ? xPositiveDirLevel : xNegativeDirLevel;
    if (!runLinearJogChunk(xDirPin, xStepPin, xPositionSteps, dirLevel, activeJogDirection, xTravelSteps, "SOFT_LIMIT_X", xAxisHomed)) {
      activeJogAxis = JOG_AXIS_NONE;
    } else {
      emitLinearPosition();
    }
    return;
  }

  if (activeJogAxis == JOG_AXIS_Y) {
    int dirLevel = activeJogDirection > 0 ? yPositiveDirLevel : yNegativeDirLevel;
    if (!runLinearJogChunk(yDirPin, yStepPin, yPositionSteps, dirLevel, activeJogDirection, yTravelSteps, "SOFT_LIMIT_Y", yAxisHomed)) {
      activeJogAxis = JOG_AXIS_NONE;
    } else {
      emitLinearPosition();
    }
  }
}

// 조그 공통 상태를 설정합니다.
void startJog(JogAxis axis, int direction) {
  jogActive = true;
  activeJogAxis = axis;
  activeJogDirection = direction;
}

// X/Y축은 현재 위치를 추적하면서 소프트 리밋을 넘지 않도록 막습니다.
bool runLinearJogChunk(int dirPin, int stepPin, long &positionSteps, int dirLevel, int directionSign, long travelSteps, const char* limitMessage, bool axisHomed) {
  digitalWrite(dirPin, dirLevel);

  for (long i = 0; i < linearJogChunkSteps; i++) {
    if (!keepMotionAlive()) {
      return false;
    }

    long nextPosition = positionSteps + directionSign;
    if (axisHomed && (nextPosition < 0 || nextPosition > travelSteps)) {
      jogActive = false;
      Serial.println(limitMessage);
      Serial.println("JOG_STOPPED");
      return false;
    }

    pulseStepPin(stepPin, currentStepDelayMicroseconds);
    positionSteps = nextPosition;
  }

  return true;
}

// 리니어 스테이지를 X, Y 순서로 원점 복귀합니다.
void homeLinearStage(bool skipXHome, bool skipYHome) {
  if (emergencyStopActive) {
    Serial.println("ERROR:ESTOP_ACTIVE");
    return;
  }

  jogActive = false;
  activeJogAxis = JOG_AXIS_NONE;
  linearStageHomed = false;
  xAxisHomed = false;
  yAxisHomed = false;
  Serial.println("LINEAR_HOME_STARTED");

  bool xOk = true;
  if (enableXAxis && !skipXHome) {
    xOk = homeSingleAxis(
      xDirPin,
      xStepPin,
      xHomePin,
      xHomeDirLevel,
      xHomeDirLevel == xPositiveDirLevel ? xNegativeDirLevel : xPositiveDirLevel,
      lround(linearHomeBackoffMm * xStepsPerMm),
      xPositionSteps
    );
  }

  bool yOk = true;
  if (enableYAxis && !skipYHome && xOk && !emergencyStopActive) {
    yOk = homeSingleAxis(
      yDirPin,
      yStepPin,
      yHomePin,
      yHomeDirLevel,
      yHomeDirLevel == yPositiveDirLevel ? yNegativeDirLevel : yPositiveDirLevel,
      lround(linearHomeBackoffMm * yStepsPerMm),
      yPositionSteps
    );
  }

  if (xOk && yOk && !emergencyStopActive) {
    xAxisHomed = enableXAxis && !skipXHome;
    yAxisHomed = enableYAxis && !skipYHome;
    linearStageHomed = xAxisHomed || yAxisHomed || ((!enableXAxis || skipXHome) && (!enableYAxis || skipYHome));
    if (xAxisHomed) {
      xPositionSteps = 0;
    }
    if (yAxisHomed) {
      yPositionSteps = 0;
    }
    emitLinearPosition();
    Serial.println("LINEAR_HOME_DONE");
  } else if (!emergencyStopActive) {
    Serial.println("ERROR:LINEAR_HOME_FAILED");
  }
}

// 단일 축에 대해 빠른 접근 -> 백오프 -> 느린 재접근 방식으로 홈 정밀도를 확보합니다.
bool homeSingleAxis(
  int dirPin,
  int stepPin,
  int limitPin,
  int homeDirLevel,
  int backoffDirLevel,
  long backoffSteps,
  long &positionSteps
) {
  unsigned long startedAt = millis();

  // 이미 센서가 눌린 상태라면 먼저 살짝 떼어냅니다.
  if (digitalRead(limitPin) == homeTriggerState) {
    digitalWrite(dirPin, backoffDirLevel);
    for (long i = 0; i < backoffSteps; i++) {
      if (!keepMotionAlive()) {
        return false;
      }
      pulseStepPin(stepPin, linearHomeFastDelayMicroseconds);
    }
  }

  // 1차 빠른 접근
  digitalWrite(dirPin, homeDirLevel);
  while (digitalRead(limitPin) != homeTriggerState) {
    if (!keepMotionAlive()) {
      return false;
    }
    if (millis() - startedAt > homeSearchTimeoutMs) {
      return false;
    }
    pulseStepPin(stepPin, linearHomeFastDelayMicroseconds);
  }
  positionSteps = 0;
  emitLinearPosition();

  // 센서를 벗어나도록 백오프
  digitalWrite(dirPin, backoffDirLevel);
  for (long i = 0; i < backoffSteps; i++) {
    if (!keepMotionAlive()) {
      return false;
    }
    pulseStepPin(stepPin, linearHomeFastDelayMicroseconds);
  }

  // 2차 느린 재접근
  startedAt = millis();
  digitalWrite(dirPin, homeDirLevel);
  while (digitalRead(limitPin) != homeTriggerState) {
    if (!keepMotionAlive()) {
      return false;
    }
    if (millis() - startedAt > homeSearchTimeoutMs) {
      return false;
    }
    pulseStepPin(stepPin, linearHomeSlowDelayMicroseconds);
  }

  positionSteps = 0;
  emitLinearPosition();
  return true;
}

// 속도(%)를 step delay로 변환합니다. 값이 클수록 더 빠르게 움직입니다.
int speedToDelay(float speedValue) {
  if (speedValue <= 0.0) {
    return defaultStepDelayMicroseconds;
  }

  float clamped = constrain(speedValue, 0.1, 100.0);
  float ratio = 0.0;

  // 저속 영역(0.1~10)에서 해상도를 더 크게 줘야 얼라인 근접 구간 감속이 실제로 체감됩니다.
  // 이전 방식은 0.x ~ 몇 단위 속도가 거의 비슷한 delay로 압축돼, UI가 감속을 걸어도 차이가 작았습니다.
  if (clamped <= 10.0) {
    ratio = (clamped / 10.0) * 0.18;
  } else if (clamped <= 35.0) {
    ratio = 0.18 + ((clamped - 10.0) / 25.0) * 0.27;
  } else {
    ratio = 0.45 + ((clamped - 35.0) / 65.0) * 0.55;
  }

  return maxStepDelayMicroseconds - (int)((maxStepDelayMicroseconds - minStepDelayMicroseconds) * ratio);
}

// 스텝 펄스를 1회 출력합니다.
void pulseStepPin(int stepPin, int stepDelayMicroseconds) {
  digitalWrite(stepPin, HIGH);
  delayMicroseconds(stepDelayMicroseconds);
  digitalWrite(stepPin, LOW);
  delayMicroseconds(stepDelayMicroseconds);
}

// 홈이 완료되지 않은 상태에서 X/Y 명령이 오면 차단합니다.
bool requireLinearHome() {
  if (linearStageHomed) {
    return true;
  }
  Serial.println("ERROR:HOME_REQUIRED");
  return false;
}

// 현재 X/Y 위치를 스텝 단위로 UI에 전달합니다.
void emitLinearPosition() {
  Serial.print("POS:X:");
  Serial.print(xPositionSteps);
  Serial.print(":Y:");
  Serial.println(yPositionSteps);
}

// X/Y 기구값으로 1mm당 필요한 스텝 수를 계산합니다.
float computeLinearStepsPerMm() {
  float mmPerRev = linearPulleyTeeth * linearBeltPitchMm;
  if (mmPerRev <= 0.0) {
    return 0.0;
  }
  float stepsPerRev = (360.0 / linearMotorStepAngleDeg) * linearMicrosteps * linearGearRatio;
  return stepsPerRev / mmPerRev;
}

// 긴 이동 중에도 즉시 E-Stop/JOG_STOP을 받을 수 있도록 간단한 명령만 선처리합니다.
bool keepMotionAlive() {
  if (emergencyStopActive || !jogActive && activeJogAxis != JOG_AXIS_NONE) {
    return false;
  }

  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "EMERGENCY_STOP") {
      emergencyStopActive = true;
      jogActive = false;
      activeJogAxis = JOG_AXIS_NONE;
      Serial.println("EMERGENCY_STOPPED");
      return false;
    }

    if (command == "JOG_STOP") {
      jogActive = false;
      activeJogAxis = JOG_AXIS_NONE;
      Serial.println("JOG_STOPPED");
      return false;
    }
  }

  return !emergencyStopActive;
}

// 지정 각도만큼 R축을 회전시킵니다.
void rotateDegrees(float degrees, int stepDelayMicroseconds) {
  if (abs(degrees) < 0.01) {
    return;
  }

  digitalWrite(rDirPin, degrees > 0 ? rCwDirLevel : rCcwDirLevel);
  long totalSteps = lround(abs(degrees) * rStepsPerDegree);

  for (long i = 0; i < totalSteps; i++) {
    if (!keepRotateAlive()) {
      Serial.println("ABORTED");
      return;
    }
    pulseStepPin(rStepPin, stepDelayMicroseconds);
  }
}

// R축 회전 중에도 E-Stop을 빠르게 반영합니다.
bool keepRotateAlive() {
  if (emergencyStopActive) {
    return false;
  }

  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    if (command == "EMERGENCY_STOP") {
      emergencyStopActive = true;
      jogActive = false;
      activeJogAxis = JOG_AXIS_NONE;
      Serial.println("EMERGENCY_STOPPED");
      return false;
    }
  }

  return !emergencyStopActive;
}

float parseTrailingFloat(String command, int prefixLength) {
  if (command.length() <= prefixLength + 1) {
    return 0.0;
  }
  if (command.charAt(prefixLength) != ':') {
    return 0.0;
  }
  return command.substring(prefixLength + 1).toFloat();
}

float parseFirstFloat(String command, int prefixLength) {
  int nextColon = command.indexOf(':', prefixLength);
  if (nextColon == -1) {
    return command.substring(prefixLength).toFloat();
  }
  return command.substring(prefixLength, nextColon).toFloat();
}

float parseSecondFloat(String command, int prefixLength, float defaultValue) {
  int nextColon = command.indexOf(':', prefixLength);
  if (nextColon == -1) {
    return defaultValue;
  }
  return command.substring(nextColon + 1).toFloat();
}
