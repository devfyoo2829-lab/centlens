"""⑥ Color Judge — 연출 3축 / 컬러 (프레임만 사용, 스크립트 무시)."""

from centlens.core.prompts import COLOR_JUDGE_PROMPT
from centlens.graph.nodes._judge_base import call_judge
from centlens.graph.state import CentLensState


async def color_judge_node(state: CentLensState) -> dict:
    """컬러 축 평가 결과를 ``color_a`` 키로 반환한다."""
    score, errors = await call_judge(
        state, "color", COLOR_JUDGE_PROMPT, use_script=False,
    )
    result: dict = {"color_a": score}
    if errors:
        result["errors"] = (state.get("errors") or []) + errors
    return result
