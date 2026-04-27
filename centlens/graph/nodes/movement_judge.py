"""② Movement Judge — 변화 3축 / 움직임."""

from centlens.core.prompts import MOVEMENT_JUDGE_PROMPT
from centlens.graph.nodes._judge_base import call_judge
from centlens.graph.state import CentLensState


async def movement_judge_node(state: CentLensState) -> dict:
    """움직임 축 평가 결과를 ``movement_a`` 키로 반환한다."""
    score, errors = await call_judge(
        state, "movement", MOVEMENT_JUDGE_PROMPT, use_script=True,
    )
    result: dict = {"movement_a": score}
    if errors:
        result["errors"] = (state.get("errors") or []) + errors
    return result
