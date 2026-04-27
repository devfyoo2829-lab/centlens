"""⑧ Cross-Check 노드 — A/B 양방향 교차 채점으로 Position Bias 제거.

A채점(6개 Judge 노드 정방향)의 결과(movement_a~sound_a)와
B채점(이 노드 역순 6축 일괄 평가) 결과의 평균을 movement_final~sound_final로 산출한다.

rationale은 A채점의 것을 그대로 사용한다 (B는 점수 검증용).
B채점이 실패하거나 일부 축이 누락되면 그 축은 A 단독, 반대도 마찬가지.
"""

import asyncio
import logging
import time
from typing import Optional

from anthropic import AsyncAnthropic

from centlens.core.prompts import CROSS_CHECK_PROMPT
from centlens.graph.nodes._judge_base import (
    CLAUDE_MODEL,
    RETRY_BACKOFFS,
    TIMEOUT_SEC,
    _build_messages,
    _coerce_axis_score,
    _parse_judge_json,
)
from centlens.graph.state import AxisScore, CentLensState

logger = logging.getLogger(__name__)


CROSS_CHECK_MAX_TOKENS: int = 2048
AXES: tuple[str, ...] = ("movement", "growth", "expansion", "camera", "color", "sound")


def _average_scores(
    a: Optional[AxisScore],
    b: Optional[AxisScore],
) -> Optional[AxisScore]:
    """A·B 점수의 평균. rationale은 A의 것을 사용. 한 쪽만 존재하면 그 쪽 그대로."""
    if a is None and b is None:
        return None
    if a is None:
        # B만 존재 — B의 score/rationale/confidence 그대로
        return {
            "score": float(b["score"]),
            "rationale": str(b["rationale"]),
            "confidence": float(b["confidence"]),
        }
    if b is None:
        return {
            "score": float(a["score"]),
            "rationale": str(a["rationale"]),
            "confidence": float(a["confidence"]),
        }
    return {
        "score": round((a["score"] + b["score"]) / 2.0, 2),
        "rationale": a["rationale"],
        "confidence": round((a["confidence"] + b["confidence"]) / 2.0, 2),
    }


async def cross_check_node(state: CentLensState) -> dict:
    """B채점(역순) 1회 호출 후 A·B 평균을 ``{axis}_final`` 키로 반환한다."""
    started = time.perf_counter()
    new_errors: list[str] = []

    frames = state.get("frames") or []
    if not frames:
        msg = "CrossCheck 실패: frames 누락"
        logger.warning("%s, 소요시간=%.2f초", msg, time.perf_counter() - started)
        return {"errors": (state.get("errors") or []) + [msg]}

    a_scores: dict[str, Optional[AxisScore]] = {
        ax: state.get(f"{ax}_a") for ax in AXES  # type: ignore[misc]
    }

    genre = state.get("genre") or ""
    script = state.get("script") or ""
    prompt_text = CROSS_CHECK_PROMPT.format(genre=genre, script=script)
    messages = _build_messages(prompt_text, frames)
    client = AsyncAnthropic()

    raw_text: Optional[str] = None
    last_exc: Optional[BaseException] = None
    for attempt, backoff in enumerate(RETRY_BACKOFFS, start=1):
        try:
            resp = await asyncio.wait_for(
                client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=CROSS_CHECK_MAX_TOKENS,
                    messages=messages,
                ),
                timeout=TIMEOUT_SEC,
            )
            parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
            raw_text = "".join(parts)
            last_exc = None
            break
        except Exception as e:
            last_exc = e
            if attempt < len(RETRY_BACKOFFS):
                await asyncio.sleep(backoff)

    b_scores: dict[str, Optional[AxisScore]] = {ax: None for ax in AXES}
    if raw_text is None:
        new_errors.append(f"CrossCheck API 실패: {last_exc}")
        logger.warning("CrossCheck API 실패: %s — A점수 단독으로 진행", last_exc)
    else:
        parsed = _parse_judge_json(raw_text)
        if not isinstance(parsed, dict):
            new_errors.append("CrossCheck 실패: JSON 파싱 실패")
            logger.warning("CrossCheck JSON 파싱 실패 — A점수 단독으로 진행")
        else:
            for ax in AXES:
                inner = parsed.get(ax)
                if isinstance(inner, dict):
                    b_scores[ax] = _coerce_axis_score(inner)

    # B 원본 점수도 state에 보존한다 — Cross-Check의 진짜 가치(같은 영상을
    # 두 관점으로 보는 것)는 B rationale에 담겨 있어 시연 자산으로 활용된다.
    result: dict = {}
    for ax in AXES:
        result[f"{ax}_b"] = b_scores[ax]
        result[f"{ax}_final"] = _average_scores(a_scores[ax], b_scores[ax])

    elapsed = time.perf_counter() - started
    n_a = sum(1 for v in a_scores.values() if v is not None)
    n_b = sum(1 for v in b_scores.values() if v is not None)
    n_final = sum(1 for ax in AXES if result[f"{ax}_final"] is not None)
    logger.info(
        "CrossCheck: A축=%d/6, B축=%d/6, 최종=%d/6, 소요시간=%.2f초",
        n_a, n_b, n_final, elapsed,
    )

    if new_errors:
        result["errors"] = (state.get("errors") or []) + new_errors
    return result
