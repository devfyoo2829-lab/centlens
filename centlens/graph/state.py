"""CentLens LangGraph StateGraph 공유 상태 스키마.

LangGraph의 StateGraph는 노드 간에 TypedDict 형태의 상태를 공유한다.
각 노드는 부분 dict를 반환하고, 프레임워크가 이를 머지하는 구조이므로
모든 키는 노드 실행 시점에 따라 점진적으로 채워진다.

- ``total=False``: 노드가 아직 실행되지 않은 단계에서는 키 자체가 없을 수 있음.
- 각 값 타입에 ``Optional``: 노드가 실패해 None을 명시적으로 채울 수 있음.
"""

from typing import Literal, Optional, TypedDict


class AxisScore(TypedDict):
    """단일 축의 평가 결과 (Judge 노드 1회 출력 단위).

    6축 Judge 노드와 Cross-Check 노드의 축별 출력이 모두 이 형식을 따른다.
    """

    score: float          # 1.0 ~ 5.0
    rationale: str        # 한국어 1~2문장 평가 근거 (프레임/스크립트 직접 인용)
    confidence: float     # 0.0 ~ 1.0


class CentLensState(TypedDict, total=False):
    """LangGraph 노드 간 공유되는 분석 상태.

    노드 진행 순서:
        ① Preprocessor → ②~⑦ 6개 Judge (병렬) → ⑧ Cross-Check
        → ⑨ Grade Calculator → ⑩ Embedder → END

    각 단계가 끝날 때마다 해당 단계의 출력 키가 채워진다.
    """

    # ── 입력 ─────────────────────────────────────────────────────────────
    video_id: Optional[str]                                  # Supabase 저장용 UUID
    video_path: Optional[str]                                # 로컬 영상 파일 경로
    category: Optional[Literal["new", "competitor", "trend"]]
    game_name: Optional[str]
    genre: Optional[str]

    # ── ① Preprocessor 출력 ─────────────────────────────────────────────
    frames: Optional[list[str]]                              # 프레임 이미지 경로 5장
    script: Optional[str]                                    # Whisper STT 결과

    # ── ②~⑦ Judge 노드 출력 (A채점, 정방향) ────────────────────────────
    movement_a: Optional[AxisScore]
    growth_a: Optional[AxisScore]
    expansion_a: Optional[AxisScore]
    camera_a: Optional[AxisScore]
    color_a: Optional[AxisScore]
    sound_a: Optional[AxisScore]

    # ── ⑧ Cross-Check 출력 (B채점 — 역순 일괄 채점 원본) ────────────────
    # B의 rationale은 시연용 자산이며 "같은 영상을 두 관점으로 본" 증거다.
    movement_b: Optional[AxisScore]
    growth_b: Optional[AxisScore]
    expansion_b: Optional[AxisScore]
    camera_b: Optional[AxisScore]
    color_b: Optional[AxisScore]
    sound_b: Optional[AxisScore]

    # ── ⑧ Cross-Check 출력 (A·B 평균 + A의 rationale 사용) ──────────────
    movement_final: Optional[AxisScore]
    growth_final: Optional[AxisScore]
    expansion_final: Optional[AxisScore]
    camera_final: Optional[AxisScore]
    color_final: Optional[AxisScore]
    sound_final: Optional[AxisScore]

    # ── ⑨ Grade Calculator 출력 ─────────────────────────────────────────
    grade: Optional[Literal["strong", "medium", "weak"]]
    weakest_axis: Optional[str]                              # 'movement' | 'growth' | ...
    total_score: Optional[float]

    # ── ⑩ Embedder 출력 ─────────────────────────────────────────────────
    embedding: Optional[list[float]]                         # 1536차원 (text-embedding-3-small)

    # ── 메타 ────────────────────────────────────────────────────────────
    errors: Optional[list[str]]                              # 노드별 실패 메시지 누적
    started_at: Optional[str]                                # ISO-8601
    completed_at: Optional[str]                              # ISO-8601
