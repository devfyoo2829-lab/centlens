"""6개 축 Judge 노드의 공통 실행 헬퍼.

각 축 노드(movement/growth/expansion/camera/color/sound)는 동일한 절차를 따른다.

    1) state 검증 (frames 존재 여부)
    2) 프롬프트 .format() — use_script=True인 축은 {script}까지 채움
    3) Claude messages.create() (이미지 + 텍스트), 60초 타임아웃, 1초→3초 백오프 2회 시도
    4) 응답 텍스트에서 JSON 추출 (raw → ```json``` 블록 → 첫{}마지막}
    5) AxisScore 형태로 정규화
    6) 시간 측정 + 로깅

각 축 노드는 `call_judge`를 한 번 호출하는 thin wrapper로 둔다.
"""

import asyncio
import json
import logging
import re
import time
from typing import Optional

from anthropic import AsyncAnthropic

from centlens.graph.state import AxisScore, CentLensState

logger = logging.getLogger(__name__)


CLAUDE_MODEL: str = "claude-sonnet-4-5"
MAX_TOKENS: int = 1024
TIMEOUT_SEC: float = 60.0

# 첫 시도 실패 후 1초 대기, 두 번째 시도 실패 후 3초 대기 (마지막 백오프는 사용되지 않지만
# 가독성 차원에서 명시). 총 2회 시도.
RETRY_BACKOFFS: tuple[float, ...] = (1.0, 3.0)


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_FIRST_LAST_BRACE_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_judge_json(raw: str) -> Optional[dict]:
    """Claude 응답에서 dict를 추출한다. 1) 전체 → 2) ```json``` 블록 → 3) 첫{ ... 마지막}."""
    if not raw:
        return None
    text = raw.strip()

    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass

    m = _JSON_FENCE_RE.search(text)
    if m:
        try:
            obj = json.loads(m.group(1))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            pass

    m2 = _FIRST_LAST_BRACE_RE.search(text)
    if m2:
        try:
            obj = json.loads(m2.group(0))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            pass

    return None


def _coerce_axis_score(obj: dict) -> Optional[AxisScore]:
    """parsed dict를 AxisScore로 정규화한다. 키 누락/범위 위반 시 None."""
    try:
        score = float(obj["score"])
        rationale = str(obj["rationale"])
        confidence = float(obj["confidence"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (1.0 <= score <= 5.0):
        return None
    if not (0.0 <= confidence <= 1.0):
        return None
    return {"score": score, "rationale": rationale, "confidence": confidence}


def _build_messages(prompt_text: str, frames_b64: list[str]) -> list[dict]:
    """Claude messages 배열 — 프레임 5장 image content + 프롬프트 text content."""
    content: list[dict] = []
    for b64 in frames_b64:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": b64,
            },
        })
    content.append({"type": "text", "text": prompt_text})
    return [{"role": "user", "content": content}]


async def call_judge(
    state: CentLensState,
    axis_name: str,
    prompt_template: str,
    *,
    use_script: bool,
) -> tuple[Optional[AxisScore], list[str]]:
    """단일 축 Judge 실행.

    Args:
        state: LangGraph 상태. ``frames`` 필수, ``genre``는 빈 문자열 허용,
            ``use_script=True``인 경우 ``script``도 사용.
        axis_name: 'movement' / 'growth' / ... — 로깅·에러 메시지 용도.
        prompt_template: 해당 축의 prompts.py 상수 (.format으로 채움).
        use_script: True면 {genre}+{script}, False면 {genre}만 채운다 (Camera/Color).

    Returns:
        (AxisScore | None, errors_list)
    """
    started = time.perf_counter()
    errors: list[str] = []
    label = axis_name.capitalize()

    frames = state.get("frames") or []
    if not frames:
        elapsed = time.perf_counter() - started
        msg = f"{label}Judge 실패: frames 누락"
        logger.warning("%s, 소요시간=%.2f초", msg, elapsed)
        errors.append(msg)
        return None, errors

    genre = state.get("genre") or ""
    if use_script:
        script = state.get("script") or ""
        prompt_text = prompt_template.format(genre=genre, script=script)
    else:
        prompt_text = prompt_template.format(genre=genre)

    messages = _build_messages(prompt_text, frames)
    client = AsyncAnthropic()

    raw_text: Optional[str] = None
    last_exc: Optional[BaseException] = None
    for attempt, backoff in enumerate(RETRY_BACKOFFS, start=1):
        try:
            resp = await asyncio.wait_for(
                client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=MAX_TOKENS,
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

    if raw_text is None:
        elapsed = time.perf_counter() - started
        logger.warning(
            "%sJudge 실패: %s, 소요시간=%.2f초", label, last_exc, elapsed,
        )
        errors.append(f"{label}Judge API 실패: {last_exc}")
        return None, errors

    parsed = _parse_judge_json(raw_text)
    score = _coerce_axis_score(parsed) if parsed is not None else None
    elapsed = time.perf_counter() - started
    if score is None:
        logger.warning(
            "%sJudge 실패: JSON 파싱 실패 또는 형식 불일치, 소요시간=%.2f초",
            label, elapsed,
        )
        errors.append(f"{label}Judge 실패: JSON 파싱 실패 또는 형식 불일치")
        return None, errors

    logger.info(
        "%sJudge: 점수=%.2f, 신뢰도=%.2f, 소요시간=%.2f초",
        label, score["score"], score["confidence"], elapsed,
    )
    return score, errors
