"""③ Growth Judge — 변화 3축 / 성장."""

from centlens.core.prompts import GROWTH_JUDGE_PROMPT
from centlens.graph.nodes._judge_base import call_judge
from centlens.graph.state import CentLensState


async def growth_judge_node(state: CentLensState) -> dict:
    """성장 축 평가 결과를 ``growth_a`` 키로 반환한다."""
    score, errors = await call_judge(
        state, "growth", GROWTH_JUDGE_PROMPT, use_script=True,
    )
    result: dict = {"growth_a": score}
    if errors:
        result["errors"] = (state.get("errors") or []) + errors
    return result
