"""④ Expansion Judge — 변화 3축 / 확장."""

from centlens.core.prompts import EXPANSION_JUDGE_PROMPT
from centlens.graph.nodes._judge_base import call_judge
from centlens.graph.state import CentLensState


async def expansion_judge_node(state: CentLensState) -> dict:
    """확장 축 평가 결과를 ``expansion_a`` 키로 반환한다."""
    score, errors = await call_judge(
        state, "expansion", EXPANSION_JUDGE_PROMPT, use_script=True,
    )
    result: dict = {"expansion_a": score}
    if errors:
        result["errors"] = (state.get("errors") or []) + errors
    return result
