"""⑤ Camera Judge — 연출 3축 / 카메라 (프레임만 사용, 스크립트 무시)."""

from centlens.core.prompts import CAMERA_JUDGE_PROMPT
from centlens.graph.nodes._judge_base import call_judge
from centlens.graph.state import CentLensState


async def camera_judge_node(state: CentLensState) -> dict:
    """카메라 축 평가 결과를 ``camera_a`` 키로 반환한다."""
    score, errors = await call_judge(
        state, "camera", CAMERA_JUDGE_PROMPT, use_script=False,
    )
    result: dict = {"camera_a": score}
    if errors:
        result["errors"] = (state.get("errors") or []) + errors
    return result
