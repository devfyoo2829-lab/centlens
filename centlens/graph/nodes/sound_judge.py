"""⑦ Sound Judge — 연출 3축 / 사운드."""

from centlens.core.prompts import SOUND_JUDGE_PROMPT
from centlens.graph.nodes._judge_base import call_judge
from centlens.graph.state import CentLensState


async def sound_judge_node(state: CentLensState) -> dict:
    """사운드 축 평가 결과를 ``sound_a`` 키로 반환한다."""
    score, errors = await call_judge(
        state, "sound", SOUND_JUDGE_PROMPT, use_script=True,
    )
    result: dict = {"sound_a": score}
    if errors:
        result["errors"] = (state.get("errors") or []) + errors
    return result
