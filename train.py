from pathlib import Path
import os

from roboflow import Roboflow
from ultralytics import YOLO


# 학습용 Roboflow API 키를 환경변수에서 읽습니다.
# 저장소에는 민감정보를 남기지 않기 위해 코드에 직접 키를 넣지 않습니다.
def get_roboflow_api_key() -> str:
    api_key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    if api_key:
        return api_key
    raise RuntimeError(
        "Roboflow API 키가 설정되지 않았습니다. "
        "학습 전 PowerShell에서 `$env:ROBOFLOW_API_KEY=\"<your_key>\"` 를 설정하세요."
    )


# Roboflow 다운로드 폴더에 data.yaml이 빠졌을 때 학습용 기본 설정을 생성합니다.
def ensure_data_yaml(dataset_dir: Path) -> Path:
    data_yaml = dataset_dir / "data.yaml"
    if data_yaml.exists():
        return data_yaml

    train_dir = dataset_dir / "train" / "images"
    val_dir = dataset_dir / "valid" / "images"
    test_dir = dataset_dir / "test" / "images"

    if not train_dir.exists() or not val_dir.exists():
        raise FileNotFoundError(
            f"학습용 데이터 폴더를 찾을 수 없습니다: '{dataset_dir}'"
        )

    lines = [
        f"path: {dataset_dir.as_posix()}",
        "train: train/images",
        "val: valid/images",
    ]
    if test_dir.exists():
        lines.append("test: test/images")

    lines.extend(
        [
            "nc: 2",
            "names:",
            "  0: Alignment Key",
            "  1: Wafer",
            "",
        ]
    )

    data_yaml.write_text("\n".join(lines), encoding="utf-8")
    print(f"[INFO] data.yaml이 없어 자동 생성했습니다: '{data_yaml}'")
    return data_yaml

def main():
    # ==========================================
    # 1. Roboflow에서 라벨링된 데이터셋 다운로드
    # ==========================================
    # Roboflow 웹사이트의 Export 탭에서 'YOLOv8' 포맷을 선택하신 후
    # "Show download code"를 눌러 나오는 코드를 아래에 입력하세요.
    
    rf = Roboflow(api_key=get_roboflow_api_key())
    project = rf.workspace("s-workspace-7ylui").project("cross_alignment_project-uyosa")
    version = project.version(1) # 다운로드받을 버전 번호
    
    # 🌟 현재 프로젝트가 '객체 탐지(Object Detection)' 타입으로 설정되어 있어 seg를 지원하지 않습니다.
    # 대신, 각도를 파악할 수 있는 OBB (회전 바운딩 박스) 포맷으로 다운로드합니다.
    dataset = version.download("yolov8-obb") 

    # 다운로드된 데이터셋의 경로를 가져옵니다
    dataset_location = Path(dataset.location).resolve()
    print(f"\n[INFO] 데이터셋이 '{dataset_location}' 에 성공적으로 다운로드 되었습니다.\n")

    # ==========================================
    # 2. YOLOv8-OBB 모델 학습 설정 및 시작
    # ==========================================
    print("[INFO] YOLOv8 OBB (회전 박스) 학습을 시작합니다...")
    data_yaml = ensure_data_yaml(dataset_location)

    # 🌟 각도를 계산해주는 OBB 전용 모델(-obb.pt)을 사용합니다!
    model = YOLO('yolov8n-obb.pt') 

    # 모델 학습 실행 (하이퍼파라미터는 필요에 맞게 수정하세요)
    # data: 데이터셋의 data.yaml 파일 경로 (Roboflow가 자동 생성한 경로 삽입)
    results = model.train(
        data=str(data_yaml),
        epochs=100,                  # 총 학습 횟수 (예: 충분한 학습을 위해 50~100 추천)
        imgsz=640,                  # 이미지 리사이즈 크기
        batch=8,                   # 그래픽카드 VRAM에 맞게 조절 (보통 8, 16, 32)
        device='0',                  # '0' (NVIDIA GPU), 'cpu' (CPU), 빈 칸('')이면 자동 선택
        project='runs/train',       # 학습 결과가 저장될 메인 디렉토리
        name='wafer_yolov8_model'   # 저장될 하위 디렉토리 (프로젝트 이름)
    )

    print("\n[INFO] 학습이 완료되었습니다!")
    print(f"[INFO] 최적의 가중치(best.pt) 파일은 'runs/train/wafer_yolov8_model/weights/best.pt' 에서 찾을 수 있습니다.")

if __name__ == '__main__':
    # Windows 환경에서 멀티프로세싱 오류를 방지하기 위해 사용합니다.
    main()
