from inference.models.utils import get_model
import supervision as sv


class WaferInferenceHelper:
    """모델 로드와 프레임 추론/주석 처리를 담당하는 보조 모듈 클래스"""

    def __init__(self, model_id="cross_alignment_project/3"):
        self.model_id = model_id
        self.model = None
        self.box_annotator = sv.BoxAnnotator()
        self.label_annotator = sv.LabelAnnotator()

    def load_model(self):
        """모델을 1회 로드"""
        if self.model is None:
            self.model = get_model(model_id=self.model_id)
        return self.model

    def infer_and_annotate(self, frame):
        """
        입력 프레임에 대해 추론 후 박스/라벨을 그려 반환
        반환:
            annotated_image, detections, results
        """
        if self.model is None:
            self.load_model()

        results = self.model.infer(frame)[0]
        detections = sv.Detections.from_inference(results)

        annotated_image = self.box_annotator.annotate(
            scene=frame.copy(),
            detections=detections
        )
        annotated_image = self.label_annotator.annotate(
            scene=annotated_image,
            detections=detections
        )

        return annotated_image, detections, results


def create_inference_helper(model_id="cross_alignment_project/3"):
    """편하게 생성하기 위한 팩토리 함수"""
    helper = WaferInferenceHelper(model_id=model_id)
    helper.load_model()
    return helper