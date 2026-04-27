"""① Preprocessor 노드 — 영상에서 프레임 5장 + Whisper STT를 추출한다.

LLM 호출은 하지 않는다. ffmpeg-python으로 프레임을 뽑고, OpenAI Whisper로
나레이션을 받아오며, 두 작업은 asyncio.gather로 병렬 실행되어 한 쪽이
실패해도 다른 쪽은 독립적으로 시도한다.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import tempfile
import time
from typing import Any

import ffmpeg
from openai import OpenAI

from centlens.core.text_utils import is_likely_hallucination
from centlens.graph.state import CentLensState

logger = logging.getLogger(__name__)


# 프레임 추출 시점 — 영상 길이 대비 비율 (0%, 5%, 25%, 50%, 95%)
FRAME_TIMESTAMPS_RATIO: tuple[float, ...] = (0.0, 0.05, 0.25, 0.50, 0.95)


def _probe_duration_sync(video_path: str) -> float:
    """ffprobe로 영상 길이(초)를 측정한다."""
    info: dict[str, Any] = ffmpeg.probe(video_path)
    return float(info["format"]["duration"])


def _extract_frames_sync(video_path: str) -> list[str]:
    """영상에서 5개 프레임을 임시 파일로 저장한 뒤 base64로 인코딩해 반환한다.

    임시 디렉토리는 컨텍스트 매니저로 관리되어 함수 종료 시 자동 삭제된다.
    """
    duration = _probe_duration_sync(video_path)
    timestamps = [duration * ratio for ratio in FRAME_TIMESTAMPS_RATIO]

    frames_b64: list[str] = []
    with tempfile.TemporaryDirectory(prefix="centlens_frames_") as tmpdir:
        for i, ts in enumerate(timestamps):
            out_path = os.path.join(tmpdir, f"{i}.jpg")
            (
                ffmpeg
                .input(video_path, ss=ts)
                .output(out_path, vframes=1, **{"q:v": 2})
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            with open(out_path, "rb") as fp:
                frames_b64.append(base64.b64encode(fp.read()).decode("ascii"))
    return frames_b64


def _transcribe_sync(video_path: str, client: OpenAI) -> str:
    """Whisper-1 동기 호출로 영상 나레이션을 텍스트로 받는다."""
    with open(video_path, "rb") as fp:
        return client.audio.transcriptions.create(
            model="whisper-1",
            file=fp,
            response_format="text",
        )


async def preprocessor_node(state: CentLensState) -> dict:
    """프레임 추출과 STT를 병렬 실행해 frames/script를 채워 반환한다.

    LangGraph 노드 시그니처: ``async (state) -> partial dict``.
    한 쪽 작업이 실패해도 다른 쪽 결과는 그대로 반환하며, 실패 사유는
    state['errors']에 누적된다.
    """
    started = time.perf_counter()
    new_errors: list[str] = []

    video_path = state.get("video_path")
    if not video_path or not os.path.isfile(video_path):
        msg = f"video_path 누락 또는 파일 미존재: {video_path!r}"
        logger.error("Preprocessor: %s", msg)
        return {
            "frames": [],
            "script": "",
            "errors": list(state.get("errors") or []) + [msg],
        }

    async def _frames_task() -> list[str]:
        try:
            return await asyncio.to_thread(_extract_frames_sync, video_path)
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
            new_errors.append(f"프레임 추출 실패: {stderr.strip()[:300]}")
            logger.exception("Preprocessor: ffmpeg frame extraction failed")
            return []
        except Exception as e:
            new_errors.append(f"프레임 추출 실패: {e}")
            logger.exception("Preprocessor: frame extraction failed")
            return []

    async def _stt_task() -> str:
        try:
            client = OpenAI()
            raw = await asyncio.to_thread(_transcribe_sync, video_path, client)
            text = (raw or "").strip()
            if is_likely_hallucination(text):
                logger.info("Preprocessor: STT 출력이 환각 패턴으로 판정되어 빈 문자열로 대체")
                return ""
            return text
        except Exception as e:
            new_errors.append(f"STT 실패: {e}")
            logger.exception("Preprocessor: Whisper STT failed")
            return ""

    frames, script = await asyncio.gather(_frames_task(), _stt_task())

    elapsed = time.perf_counter() - started
    logger.info(
        "Preprocessor: 영상=%s, 프레임=%d장, 스크립트=%d자, 소요시간=%.2f초",
        video_path, len(frames), len(script), elapsed,
    )

    return {
        "frames": frames,
        "script": script,
        "errors": list(state.get("errors") or []) + new_errors,
    }
