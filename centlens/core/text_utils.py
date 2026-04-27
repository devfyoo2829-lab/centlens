"""공용 텍스트 유틸리티 — Whisper 환각 필터 등.

본 모듈은 preprocessor 노드와 prepare_data 스크립트가 동일한 환각 판정 로직을
공유하기 위한 single source of truth 이다.
"""

from __future__ import annotations

import re
from collections import Counter


# Whisper-1이 무음 또는 음성이 거의 없는 영상에 대해 자주 출력하는
# YouTube 보일러플레이트 패턴(소문자 비교).
_HALLUCINATION_SUBSTRINGS: tuple[str, ...] = (
    "구독해주세요",
    "구독 부탁",
    "시청해주셔서 감사",
    "다음 영상에서",
    "좋아요와 구독",
    "thanks for watching",
    "thank you for watching",
    "please subscribe",
    "subscribe to",
    "[음악]",
    "[music]",
    "mbc 뉴스",
)


def is_likely_hallucination(text: str) -> bool:
    """Whisper STT 결과가 환각으로 추정되는지 판정한다.

    무음/저음 영상에서 Whisper-1이 출력하는 YouTube 보일러플레이트
    (구독/시청 감사 등)와 동일 문장 3회 이상 반복을 환각으로 본다.
    """
    if not text:
        return False
    cleaned = text.strip().lower()
    if not cleaned:
        return False

    for pat in _HALLUCINATION_SUBSTRINGS:
        if pat in cleaned:
            return True

    sentences = [s.strip() for s in re.split(r"[.!?。]", cleaned) if s.strip()]
    if len(sentences) >= 3:
        most_common = Counter(sentences).most_common(1)
        if most_common and most_common[0][1] >= 3:
            return True

    return False
