"""⑩ Embedder — 6축 근거 텍스트를 OpenAI text-embedding-3-small로 1536차원 임베딩.

LLM 호출은 하지 않으며, OpenAI Embeddings API만 호출한다.
시맨틱 검색용 텍스트는 게임명·장르·등급·6축 rationale을 합쳐 구성한다.
"""

import asyncio
import logging
import time
from typing import Optional

from openai import AsyncOpenAI

from centlens.graph.state import AxisScore, CentLensState

logger = logging.getLogger(__name__)


EMBED_MODEL: str = "text-embedding-3-small"
EMBED_TIMEOUT_SEC: float = 30.0
AXES: tuple[str, ...] = ("movement", "growth", "expansion", "camera", "color", "sound")
AXIS_KO: dict[str, str] = {
    "movement": "움직임",
    "growth": "성장",
    "expansion": "확장",
    "camera": "카메라",
    "color": "컬러",
    "sound": "사운드",
}


def _build_embed_text(state: CentLensState) -> str:
    """게임명/장르/등급 헤더 + 6축 rationale 본문으로 임베딩 입력 텍스트를 만든다."""
    game = state.get("game_name") or ""
    genre = state.get("genre") or ""
    grade = state.get("grade") or ""
    lines = [f"[{game}] [{genre}] [{grade}]"]
    for ax in AXES:
        v: Optional[AxisScore] = state.get(f"{ax}_final")  # type: ignore[assignment]
        rationale = v["rationale"] if v else ""
        lines.append(f"{AXIS_KO[ax]}: {rationale}")
    return "\n".join(lines)


async def embedder_node(state: CentLensState) -> dict:
    """텍스트 합성 → text-embedding-3-small 호출 → ``embedding`` 키로 반환."""
    started = time.perf_counter()
    text = _build_embed_text(state)

    if not text.strip() or all(line.split(":", 1)[-1].strip() == "" for line in text.splitlines()[1:]):
        # 헤더만 있고 6축 rationale이 전부 빈 경우 — 임베딩할 의미 있는 내용이 없음
        msg = "Embedder 실패: 임베딩 입력 텍스트가 비어 있음"
        logger.warning("%s, 소요시간=%.4f초", msg, time.perf_counter() - started)
        return {
            "embedding": None,
            "errors": (state.get("errors") or []) + [msg],
        }

    try:
        client = AsyncOpenAI()
        resp = await asyncio.wait_for(
            client.embeddings.create(model=EMBED_MODEL, input=text),
            timeout=EMBED_TIMEOUT_SEC,
        )
        vec = list(resp.data[0].embedding)
    except Exception as e:
        elapsed = time.perf_counter() - started
        msg = f"Embedder 실패: {e}"
        logger.warning("%s, 소요시간=%.4f초", msg, elapsed)
        return {
            "embedding": None,
            "errors": (state.get("errors") or []) + [msg],
        }

    elapsed = time.perf_counter() - started
    logger.info(
        "Embedder: 차원=%d, 텍스트=%d자, 소요시간=%.2f초",
        len(vec), len(text), elapsed,
    )
    return {"embedding": vec}
