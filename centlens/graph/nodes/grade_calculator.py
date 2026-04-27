"""⑨ Grade Calculator — weakest-link 수식으로 등급 산출 (LLM 호출 없음).

LangGraph "노드는 모두 async" 규칙에 맞춰 async로 정의하되 본체는 순수 동기 계산이다.
"""

import logging
import time
from typing import Optional

from centlens.graph.state import AxisScore, CentLensState

logger = logging.getLogger(__name__)


AXES: tuple[str, ...] = ("movement", "growth", "expansion", "camera", "color", "sound")


async def grade_calculator_node(state: CentLensState) -> dict:
    """6축 ``{axis}_final`` 점수를 weakest-link로 종합 등급으로 변환한다.

    누락된 축은 0점으로 간주(가장 보수적). 어느 한 축이라도 누락되면
    `weak`이 강제되며, 누락 사실을 errors에 기록한다.
    """
    started = time.perf_counter()

    scores: dict[str, float] = {}
    missing: list[str] = []
    for ax in AXES:
        v: Optional[AxisScore] = state.get(f"{ax}_final")  # type: ignore[assignment]
        if v is None:
            scores[ax] = 0.0
            missing.append(ax)
        else:
            scores[ax] = float(v["score"])

    min_score = min(scores.values())
    total = round(sum(scores.values()), 2)
    weakest = min(scores, key=lambda k: scores[k])

    if min_score >= 4 and total >= 24:
        grade = "strong"
    elif min_score >= 3 and total >= 18:
        grade = "medium"
    else:
        grade = "weak"

    elapsed = time.perf_counter() - started
    if missing:
        logger.warning(
            "GradeCalculator: %d개 축 누락(%s) — 0점 처리, 등급=%s, 합계=%.2f, "
            "최약축=%s, 소요시간=%.4f초",
            len(missing), ",".join(missing), grade, total, weakest, elapsed,
        )
    else:
        logger.info(
            "GradeCalculator: 등급=%s, 최약축=%s, 합계=%.2f, 소요시간=%.4f초",
            grade, weakest, total, elapsed,
        )

    result: dict = {
        "grade": grade,
        "weakest_axis": weakest,
        "total_score": total,
    }
    if missing:
        msg = f"GradeCalculator: 축 누락({','.join(missing)}) — 0점 처리"
        result["errors"] = (state.get("errors") or []) + [msg]
    return result
