"""페이지 1: 새 영상 분석 — 실제 LangGraph 호출 + 실시간 노드 진행 + 자동 페이지 2 이동.

3가지 입력 옵션:
  A. 영상 파일 업로드 (MP4 ≤ 200MB)
  B. YouTube URL (yt-dlp로 다운로드)
  C. 기존 5편 중 재분석 (시연용 빠른 옵션)

분석 시작 클릭 → asyncio.run() 으로 ``compiled.astream(stream_mode="updates")`` 호출 →
각 노드 완료 시 single placeholder에 진행 상황 incremental 갱신 → 완료 후
``demo_cache/{slug}.json`` 갱신 + 페이지 2로 자동 이동.
"""

import asyncio
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from centlens.core.repository import (  # noqa: E402
    AxisTriplet,
    VideoRecord,
    get_repository,
    sha256_file,
)
from centlens.ui.styles import (  # noqa: E402
    AXES,
    AXIS_KO,
    CATEGORY_KO,
    configure_page,
    render_header,
    tip_html,
)


configure_page(page_title="새 영상 분석 · CentLens")
render_header(active="upload")


# ─── 그래프 인스턴스 캐시 ────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _compiled_graph():
    """LangGraph StateGraph 컴파일은 ~1초 — 세션 내 1회만 수행."""
    from centlens.graph.builder import build_centlens_graph
    return build_centlens_graph()


# ─── 노드 메타 ────────────────────────────────────────────────────────────────
ALL_NODES: tuple[str, ...] = (
    "preprocessor",
    "movement_judge", "growth_judge", "expansion_judge",
    "camera_judge", "color_judge", "sound_judge",
    "cross_check", "grade_calculator", "embedder",
)
JUDGE_NODES: tuple[str, ...] = tuple(f"{ax}_judge" for ax in AXES)
JUDGE_NODE_TO_KO: dict[str, str] = {f"{ax}_judge": AXIS_KO[ax] for ax in AXES}


# ─── 페이지 타이틀 + 소개 카드 ────────────────────────────────────────────────
st.markdown(
    """
    <div style="margin-bottom:16px;">
      <h1>새 영상 분석</h1>
    </div>
    <div class="cl-intro-card">
      <h3>광고 집행 전, 6축으로 먼저 점검합니다</h3>
      <p>
        CentLens는 슈퍼센트의 <strong>광고 사전 분석 도구</strong>입니다.
        영상이 슈퍼센트가 중요하게 보는 6가지 축 —
        <strong>움직임·성장·확장·카메라·컬러·사운드</strong> — 에서
        어떤 강점과 약점을 가지는지 약 30~40초 안에 진단해,
        집행 전에 보완할 지점을 찾을 수 있도록 돕습니다.
      </p>
      <p class="cl-intro-hint">
        분석 1편당 API 비용이 소모됩니다 (약 $0.05~$0.10).
        기능을 살펴보는 목적이라면 아래 <strong>기존 영상 재분석</strong>
        옵션 사용을 권장합니다.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ─── 데이터 소스 ──────────────────────────────────────────────────────────────
repo = get_repository()
existing_records: list[VideoRecord] = repo.list_videos()


# ─── 2 컬럼: 영상 입력 / 분류·메타 ───────────────────────────────────────────
col_video, col_meta = st.columns(2)

with col_video:
    st.markdown(
        '<div class="cl-card">'
        '<div class="cl-card-head">영상 입력</div>',
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader(
        "MP4 / 최대 200MB",
        type=["mp4"],
        accept_multiple_files=False,
        label_visibility="collapsed",
        key="upload_file",
    )

    st.markdown(
        '<div style="display:flex; align-items:center; gap:8px; font-size:12px; color:#71717a; margin:12px 0;">'
        '<div style="flex:1; height:0.5px; background:#262626;"></div>'
        "<span>또는</span>"
        '<div style="flex:1; height:0.5px; background:#262626;"></div>'
        "</div>",
        unsafe_allow_html=True,
    )
    youtube_url = st.text_input(
        "YouTube URL 붙여넣기",
        placeholder="YouTube URL 붙여넣기",
        label_visibility="collapsed",
        key="upload_url",
    )

    st.markdown(
        '<div style="display:flex; align-items:center; gap:8px; font-size:12px; color:#71717a; margin:12px 0;">'
        '<div style="flex:1; height:0.5px; background:#262626;"></div>'
        "<span>또는</span>"
        '<div style="flex:1; height:0.5px; background:#262626;"></div>'
        "</div>",
        unsafe_allow_html=True,
    )
    sel_existing = st.selectbox(
        "기존 영상 재분석",
        options=[None] + list(existing_records),
        format_func=(
            lambda r: "— 기존 영상 선택 (시연 권장)" if r is None
            else f"{r.game_name} · {CATEGORY_KO.get(r.category, r.category)} · {r.genre}"
        ),
        index=0,
        label_visibility="collapsed",
        key="upload_existing",
    )
    st.markdown("</div>", unsafe_allow_html=True)


# ─── 옵션 C 선택 → 메타 자동 입력 ────────────────────────────────────────────
# Streamlit text_input의 ``value`` 인자는 첫 렌더에만 적용되므로 session_state 를
# 직접 변경해야 한다. selectbox 가 바뀐 시점에 같은 키를 갱신.
_sel_slug = sel_existing.slug if sel_existing is not None else None
_last_sel_slug = st.session_state.get("_last_sel_slug")
if _sel_slug != _last_sel_slug:
    if sel_existing is not None:
        st.session_state["upload_game_name"] = sel_existing.game_name
        st.session_state["upload_genre"] = sel_existing.genre
        st.session_state["upload_category"] = sel_existing.category
    else:
        # 옵션 C 해제 — input 비움
        st.session_state["upload_game_name"] = ""
        st.session_state["upload_genre"] = ""
        st.session_state["upload_category"] = "new"
    st.session_state["_last_sel_slug"] = _sel_slug


with col_meta:
    st.markdown(
        '<div class="cl-card">'
        '<div class="cl-card-head">분류 및 메타데이터</div>',
        unsafe_allow_html=True,
    )
    # session_state 가 위에서 동기화됐으므로 default/value 인자는 제거 — key 만 사용
    if "upload_category" not in st.session_state:
        st.session_state["upload_category"] = "new"

    st.markdown(
        f'<div style="display:flex; align-items:center; margin: 0 0 6px;">'
        f'<label style="font-size:12px; color:#71717a;">분류</label>'
        f'{tip_html("분류는 왜 중요한가요?", "나중에 자사·경쟁사·시장 트렌드를 비교 분석할 때 기준이 돼요. 의미 검색에서도 분류로 필터링할 수 있어요.")}'
        "</div>",
        unsafe_allow_html=True,
    )
    # st.segmented_control 의 active 표시가 일부 빌드에서 시각적으로 약해 보여
    # st.button 3개 + type='primary'/'secondary' 로 명시적 active 시각화.
    cat_cols = st.columns(3)
    for idx, cat_key in enumerate(CATEGORY_KO.keys()):
        is_active = st.session_state.get("upload_category") == cat_key
        if cat_cols[idx].button(
            CATEGORY_KO[cat_key],
            key=f"cat_btn_{cat_key}",
            type="primary" if is_active else "secondary",
            use_container_width=True,
        ):
            st.session_state["upload_category"] = cat_key
            st.rerun()
    category_key = st.session_state["upload_category"]

    st.markdown(
        '<label style="font-size:12px; color:#71717a; display:block; margin: 14px 0 6px;">게임명</label>',
        unsafe_allow_html=True,
    )
    game_name = st.text_input(
        "게임명",
        placeholder="Pizza Ready",
        label_visibility="collapsed",
        key="upload_game_name",
    )

    st.markdown(
        f'<div style="display:flex; align-items:center; margin: 14px 0 6px;">'
        f'<label style="font-size:12px; color:#71717a;">장르</label>'
        f'{tip_html("장르 입력 팁", "&quot;하이퍼캐주얼&quot;, &quot;전략&quot;, &quot;퍼즐&quot; 등 자유롭게 입력하세요. AI가 평가할 때 장르 특성을 고려합니다.")}'
        "</div>",
        unsafe_allow_html=True,
    )
    genre = st.text_input(
        "장르",
        placeholder="하이퍼캐주얼",
        label_visibility="collapsed",
        key="upload_genre",
    )
    st.markdown("</div>", unsafe_allow_html=True)


# ─── 분석 시작 버튼 ──────────────────────────────────────────────────────────
st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
start_clicked = st.button(
    "분석 시작",
    type="primary",
    use_container_width=True,
    key="start_analysis",
)


# ─── 진행 상황 placeholder + 헬퍼 ────────────────────────────────────────────
progress_placeholder = st.empty()
status_placeholder = st.empty()


# ─── 매칭 카드 렌더 (분기 밖 — start_clicked 와 무관하게 살아있음) ───────────
# 검증 분기에서 ``session_state["pending_match"]`` 에 결과를 저장하면
# 다음 rerun 에서 여기에서 카드 + 두 버튼이 그려진다.
def _render_pending_match() -> None:
    pm = st.session_state.get("pending_match")
    if not pm:
        return

    matched_slug: str = pm["matched_slug"]
    matched_game: str = pm["matched_game"]
    matched_category: str = pm["matched_category"]
    matched_genre: str = pm.get("matched_genre") or "—"
    match_sim: float = pm["match_sim"]
    match_reason: str = pm["match_reason"]
    target_slug: str = pm.get("target_slug") or matched_slug

    cat_ko_match = CATEGORY_KO.get(matched_category, matched_category)
    sim_str = f"{match_sim:.4f}" if match_sim < 1.0 else "1.0000 (동일 파일)"
    warn_html = (
        '<div class="cl-similarity-warning">'
        '<div class="cl-sim-title">⚠ 이미 분석된 영상입니다</div>'
        f'<div class="cl-sim-meta">매칭: <strong>{matched_game}</strong> '
        f'({cat_ko_match} · {matched_genre})</div>'
        f'<div class="cl-sim-meta">근거: {match_reason}</div>'
        f'<div class="cl-sim-meta">유사도: <span class="cl-num">{sim_str}</span> '
        f'(threshold ≥ 0.95)</div>'
        '</div>'
    )
    st.markdown(warn_html, unsafe_allow_html=True)

    sim_cols = st.columns(2)
    with sim_cols[0]:
        if st.button("기존 결과 보기", type="primary",
                     key=f"sim_open_{matched_slug}",
                     use_container_width=True):
            st.session_state["nav_slug"] = matched_slug
            st.query_params["slug"] = matched_slug
            st.session_state.pop("pending_match", None)
            st.switch_page("pages/2_detail.py")
    with sim_cols[1]:
        if st.button("강제 재분석", key=f"sim_force_{target_slug}",
                     use_container_width=True):
            st.session_state["force_reanalyze"] = target_slug
            st.session_state.pop("pending_match", None)
            st.rerun()
    st.stop()


_render_pending_match()


def _step_row(state: str, label: str, duration: Optional[float] = None,
              tip_t: str = "", tip_b: str = "") -> str:
    """state: 'done' | 'running' | 'pending'."""
    if state == "done":
        icon = '<div style="width:16px; height:16px; background:#00d68f; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:10px; color:#000;">✓</div>'
        text_color = "#fff"
    elif state == "running":
        icon = '<div style="width:14px; height:14px; border:1.5px solid #f5a524; border-top-color:transparent; border-radius:50%;"></div>'
        text_color = "#fff"
    else:
        icon = '<div style="width:16px; height:16px; border:0.5px solid #404040; border-radius:50%;"></div>'
        text_color = "#a1a1aa"

    tip_inline = tip_html(tip_t, tip_b) if tip_t else ""
    if duration is not None:
        right = f'<span style="font-size:12px; color:#71717a; font-family:&quot;JetBrains Mono&quot;, monospace;">{duration:.1f}초</span>'
    elif state == "running":
        right = '<span style="font-size:12px; color:#f5a524;">진행 중</span>'
    else:
        right = '<span style="font-size:12px; color:#71717a;">대기</span>'
    return (
        f'<div style="display:flex; align-items:center; gap:12px; padding:8px 12px; background:#000; border-radius:6px; border:0.5px solid #262626;">'
        f"{icon}"
        f'<div style="flex:1; display:flex; align-items:center;">'
        f'<span style="font-size:13px; color:{text_color};">{label}</span>'
        f"{tip_inline}"
        "</div>"
        f"{right}"
        "</div>"
    )


def _axis_chip(state: str, ko_name: str) -> str:
    if state == "done":
        dot = '<div style="width:12px; height:12px; background:#00d68f; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:8px; color:#000;">✓</div>'
        border = "#262626"
    elif state == "running":
        dot = '<div style="width:12px; height:12px; border:1.5px solid #f5a524; border-top-color:transparent; border-radius:50%;"></div>'
        border = "#404040"
    else:
        dot = '<div style="width:12px; height:12px; border:0.5px solid #404040; border-radius:50%;"></div>'
        border = "#262626"
    return (
        f'<div style="display:flex; align-items:center; gap:8px; padding:8px 10px; background:#0a0a0a; border-radius:4px; border:0.5px solid {border};">'
        f"{dot}"
        f'<div><div style="font-size:11px; color:#fff;">{ko_name}</div></div>'
        "</div>"
    )


def _render_progress(
    placeholder: Any,
    node_states: dict[str, str],
    durations: dict[str, float],
) -> None:
    """진행 상황 카드 전체를 placeholder에 incremental 렌더."""
    completed = sum(1 for s in node_states.values() if s == "done")

    axis_chips = "".join(
        _axis_chip(node_states.get(f"{ax}_judge", "pending"), AXIS_KO[ax])
        for ax in AXES
    )
    judge_done = sum(1 for n in JUDGE_NODES if node_states.get(n) == "done")
    judge_any_running = any(node_states.get(n) == "running" for n in JUDGE_NODES)
    judge_label_state = "완료" if judge_done == 6 else ("중" if judge_any_running else "대기")

    rows: list[str] = []
    rows.append(_step_row(
        node_states.get("preprocessor", "pending"),
        "영상 준비",
        duration=durations.get("preprocessor"),
        tip_t="영상 준비 단계",
        tip_b="영상에서 5장면(0%/5%/25%/50%/95% 지점)을 추출하고, 음성을 텍스트로 변환해요. AI가 영상 내용을 이해하기 위한 사전 작업입니다.",
    ))
    rows.append(
        f'<div style="padding:12px; background:#000; border-radius:6px; border:0.5px solid #262626;">'
        '<div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">'
        '<div style="display:flex; align-items:center;">'
        f'<span class="cl-label-upper" style="color:#71717a;">6축 평가 (병렬 실행 {judge_label_state})</span>'
        f'{tip_html("6축이 뭔가요?", "슈퍼센트 자체 평가 프레임이에요. 변화 3축(움직임·성장·확장)은 시선을 끄는 요소를, 연출 3축(카메라·컬러·사운드)은 메시지 전달을 평가합니다.")}'
        "</div>"
        f'<span style="font-size:11px; color:#71717a;">{judge_done} / 6 완료</span>'
        "</div>"
        '<p style="font-size:11px; color:#71717a; margin: 0 0 10px;">변화 3축과 연출 3축을 동시에 평가합니다.</p>'
        f'<div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:6px;">{axis_chips}</div>'
        "</div>"
    )
    rows.append(_step_row(
        node_states.get("cross_check", "pending"),
        "교차 검증",
        duration=durations.get("cross_check"),
        tip_t="교차 검증이 뭔가요?",
        tip_b="같은 영상을 6축을 한꺼번에, 다른 순서로 다시 평가해요. 1차 평가의 점수 편향을 줄이는 역할입니다. 두 결과를 비교해서 점수 차이가 큰 축을 찾아냅니다.",
    ))
    rows.append(_step_row(
        node_states.get("grade_calculator", "pending"),
        "등급 산출",
        duration=durations.get("grade_calculator"),
        tip_t="등급은 어떻게 결정되나요?",
        tip_b="6축 모두 4점 이상이면 우수, 3점 이상이면 보통, 그 외는 약함이에요. 한 축이라도 약하면 전체 등급이 낮아져요 (가장 약한 축이 기준).",
    ))
    rows.append(_step_row(
        node_states.get("embedder", "pending"),
        "검색 인덱싱",
        duration=durations.get("embedder"),
        tip_t="검색 인덱싱이 뭔가요?",
        tip_b="나중에 \"사운드가 약한 영상\" 같은 자연스러운 표현으로 비슷한 영상을 찾을 수 있도록, 영상 내용을 의미 기반으로 정리해두는 단계예요.",
    ))

    placeholder.markdown(
        f"""
        <div class="cl-card">
          <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
            <div style="display:flex; align-items:center;">
              <span style="font-size:13px; font-weight:500; color:#fff;">분석 진행 상황</span>
              {tip_html("분석은 어떻게 진행되나요?", "영상을 5장면으로 쪼개고, 6개 축을 동시에 평가한 뒤, 점수 편향을 줄이기 위해 한 번 더 검증해요. 마지막에 종합 등급을 산출합니다.")}
            </div>
            <div style="font-size:12px; color:#71717a;">{completed} / 10 단계 완료</div>
          </div>
          <p style="font-size:11px; color:#71717a; margin: 0 0 16px;">영상 한 편을 6축 프레임으로 평가하는 데 약 30~40초 걸려요.</p>
          <div style="display:flex; flex-direction:column; gap:8px;">
            {''.join(rows)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── slug / 영상 파일 결정 ────────────────────────────────────────────────────
def _make_slug(name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return f"{base or 'upload'}_{int(time.time())}"


def _save_uploaded_to_videos(uploaded_file, slug: str) -> Path:
    target = _PROJECT_ROOT / "data" / "videos" / f"{slug}.mp4"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(uploaded_file.getvalue())
    return target


_DEFAULT_DURATION_SEC_FALLBACK: float = 30.0


def _probe_duration_safe(video_path: Path) -> float:
    """영상 길이 측정 — ffprobe → cv2 → moviepy → 30.0초 기본값 폴백.

    Streamlit Cloud 같이 ffprobe 바이너리가 없는 환경에서도 분석 흐름이 멈추지 않게 한다.
    """
    # 1) ffprobe subprocess
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
            capture_output=True, text=True, check=True, timeout=30,
        )
        return float(probe.stdout.strip())
    except Exception:
        pass

    # 2) OpenCV
    try:
        import cv2  # type: ignore[import-not-found]
        cap = cv2.VideoCapture(str(video_path))
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            if fps and fps > 0 and frame_count and frame_count > 0:
                return float(frame_count) / float(fps)
    except Exception:
        pass

    # 3) moviepy
    try:
        from moviepy.editor import VideoFileClip  # type: ignore[import-not-found]
        with VideoFileClip(str(video_path)) as clip:
            return float(clip.duration)
    except Exception:
        pass

    # 4) 기본값
    return _DEFAULT_DURATION_SEC_FALLBACK


def _extract_frames_to_disk(video_path: Path, slug: str) -> None:
    """ffmpeg로 0%/5%/25%/50%/95% 시점 5장을 ``data/frames/{slug}/{0-4}.jpg`` 에 저장.

    preprocessor 노드는 base64를 메모리에서만 다루므로, 페이지 2(``_frame_data_uri``)가
    디스크에서 frames를 읽을 수 있도록 별도 디스크 사본을 만든다. 옵션 A(파일 업로드)와
    B(YouTube)에서 호출. 옵션 C는 기존 frames 가 이미 디스크에 있어 호출 불필요.

    duration 측정이 실패해도 30초 기본값으로 진행 (분석 자체는 멈추지 않음).
    """
    target_dir = _PROJECT_ROOT / "data" / "frames" / slug
    target_dir.mkdir(parents=True, exist_ok=True)

    duration = _probe_duration_safe(video_path)
    timestamps = [0.0, duration * 0.05, duration * 0.25, duration * 0.50, duration * 0.95]

    for i, ts in enumerate(timestamps):
        out_path = target_dir / f"{i}.jpg"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-ss", f"{ts:.3f}", "-i", str(video_path),
                 "-vframes", "1", "-q:v", "2", str(out_path)],
                capture_output=True, check=True, timeout=30,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            # ffmpeg 자체가 없는 환경 — frame 추출 skip. preprocessor 노드는 ffmpeg-python 으로
            # 별도 base64 추출을 시도하니 이 함수가 실패해도 분석은 계속됨.
            return


# ─── 시드 영상 매칭 (yt-dlp 우회) ────────────────────────────────────────────
# 슈퍼센트 공식 광고 5편의 원본 URL → 로컬 mp4 slug 매핑.
# 사용자가 옵션 B(YouTube URL)로 시드 영상 URL을 입력하면 yt-dlp 다운로드 대신
# 이미 ``data/videos/`` 에 있는 시드 mp4를 그대로 재사용 (네트워크 의존성 제거).
SEED_URL_MAP: dict[str, str] = {
    # YouTube video_id (?v=...)
    "z6uoNzTQqsI": "burger_please_drive_thru",
    "2sXUK_X97jc": "pizza_ready_break",
    "CA0Iw_q-r_g": "snake_clash_morph",
    "FZ5HF8erSXI": "twerk_race_gate",
    # Facebook video id (/videos/...)
    "1944219636114772": "kingshot_expansion",
}


def _match_seed_video(url: str) -> Optional[str]:
    """URL 에서 video_id 를 추출해 ``SEED_URL_MAP`` 매칭. 매칭되면 시드 slug, 없으면 None.

    매칭 시도 순서:
        1) ``SEED_URL_MAP`` 의 모든 ID 가 URL 문자열에 포함되는지 (가장 robust)
        2) ``v=`` 쿼리 파라미터로 추출한 YouTube ID
    """
    if not url:
        return None
    for vid_id, seed_slug in SEED_URL_MAP.items():
        if vid_id in url:
            return seed_slug
    return None


def _download_youtube(url: str, slug: str, status_box: Any) -> Path:
    # ── 시드 매칭 (yt-dlp 우회) — 시드 영상 URL 이면 로컬 파일 그대로 사용 ──
    seed_slug = _match_seed_video(url)
    if seed_slug is not None:
        local_path = _PROJECT_ROOT / "data" / "videos" / f"{seed_slug}.mp4"
        if local_path.is_file():
            status_box.info(
                f"시드 영상 매칭 — 로컬 파일 사용 ({seed_slug}.mp4, yt-dlp 우회)"
            )
            return local_path
        # 시드인데 파일이 없으면 경고 후 yt-dlp 시도
        status_box.warning(
            f"시드 매칭됐지만 로컬 파일 없음: {local_path}. yt-dlp 다운로드로 폴백합니다."
        )

    target = _PROJECT_ROOT / "data" / "videos" / f"{slug}.mp4"
    target.parent.mkdir(parents=True, exist_ok=True)
    status_box.info("YouTube 영상 다운로드 중… (보통 10~30초)")
    cmd = [
        "yt-dlp",
        "-f", "best[ext=mp4][height<=720]/best[ext=mp4]/best",
        "-o", str(target),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp 실패: {result.stderr.strip()[:200]}")
    if not target.is_file():
        raise RuntimeError("yt-dlp가 파일을 만들지 못했습니다.")
    return target


# ─── 실시간 그래프 실행 ──────────────────────────────────────────────────────
async def _run_analysis_realtime(
    slug: str,
    video_path: Path,
    metadata: dict,
    placeholder: Any,
) -> tuple[dict, dict, float]:
    compiled = _compiled_graph()
    initial_state: dict[str, Any] = {
        "video_id": str(uuid.uuid4()),
        "video_path": str(video_path),
        "category": metadata["category"],
        "game_name": metadata["game_name"],
        "genre": metadata["genre"],
        "errors": [],
    }
    config: dict[str, Any] = {
        "run_name": f"centlens:{slug}",
        "tags": ["centlens", "page_1_live", slug, metadata["category"]],
        "metadata": {"slug": slug, **metadata},
    }

    started = time.perf_counter()
    node_end_t: dict[str, float] = {}
    node_states: dict[str, str] = {n: "pending" for n in ALL_NODES}
    node_states["preprocessor"] = "running"
    durations: dict[str, float] = {}
    final_state: dict[str, Any] = dict(initial_state)

    _render_progress(placeholder, node_states, durations)

    async for chunk in compiled.astream(initial_state, stream_mode="updates", config=config):
        now = time.perf_counter() - started
        if not isinstance(chunk, dict):
            continue
        for node_name, update in chunk.items():
            node_end_t[node_name] = now
            node_states[node_name] = "done"

            if isinstance(update, dict):
                for k, v in update.items():
                    final_state[k] = v

            # 노드별 duration 산출 + 다음 단계 'running' 표시
            if node_name == "preprocessor":
                durations["preprocessor"] = now
                for jn in JUDGE_NODES:
                    if node_states[jn] == "pending":
                        node_states[jn] = "running"
            elif node_name in JUDGE_NODES:
                pre_t = node_end_t.get("preprocessor", 0)
                durations[node_name] = max(0.0, now - pre_t)
                if all(jn in node_end_t for jn in JUDGE_NODES):
                    node_states["cross_check"] = "running"
            elif node_name == "cross_check":
                judge_max = max((node_end_t[jn] for jn in JUDGE_NODES if jn in node_end_t), default=0)
                durations["cross_check"] = max(0.0, now - judge_max)
                node_states["grade_calculator"] = "running"
            elif node_name == "grade_calculator":
                durations["grade_calculator"] = max(0.0, now - node_end_t.get("cross_check", 0))
                node_states["embedder"] = "running"
            elif node_name == "embedder":
                durations["embedder"] = max(0.0, now - node_end_t.get("grade_calculator", 0))

            _render_progress(placeholder, node_states, durations)

    return final_state, durations, time.perf_counter() - started


def _state_to_record(
    slug: str,
    metadata: dict,
    final_state: dict,
    durations: dict,
    total_elapsed: float,
    started_iso: str,
) -> VideoRecord:
    axis_scores = {}
    for ax in AXES:
        axis_scores[ax] = AxisTriplet(
            a=final_state.get(f"{ax}_a"),
            b=final_state.get(f"{ax}_b"),
            final=final_state.get(f"{ax}_final"),
        )
    embedding = final_state.get("embedding")
    return VideoRecord(
        slug=slug,
        game_name=metadata["game_name"],
        genre=metadata["genre"],
        category=metadata["category"],
        publisher=metadata.get("publisher"),
        axis_scores=axis_scores,
        grade=final_state.get("grade"),
        weakest_axis=final_state.get("weakest_axis"),
        total_score=final_state.get("total_score"),
        durations_sec={k: round(v, 3) for k, v in durations.items()},
        total_elapsed_sec=round(total_elapsed, 2),
        started_at=started_iso,
        errors=list(final_state.get("errors") or []),
        embedding=list(embedding) if embedding else None,
        embedding_dim=len(embedding) if embedding else None,
    )


# ─── 클릭 시 실행 흐름 ────────────────────────────────────────────────────────
if start_clicked:
    # 입력 우선순위: 기존 영상(C) → 업로드(A) → URL(B)
    if not game_name or not genre:
        status_placeholder.warning("게임명과 장르를 입력해주세요.")
        st.stop()

    try:
        if sel_existing is not None:
            slug = sel_existing.slug
            video_path = _PROJECT_ROOT / "data" / "videos" / f"{slug}.mp4"
            if not video_path.is_file():
                raise RuntimeError(f"기존 영상 파일이 없음: {video_path}")
        elif uploaded is not None:
            slug = _make_slug(game_name)
            video_path = _save_uploaded_to_videos(uploaded, slug)
            _extract_frames_to_disk(video_path, slug)
        elif youtube_url and youtube_url.strip():
            slug = _make_slug(game_name)
            video_path = _download_youtube(youtube_url.strip(), slug, status_placeholder)
            _extract_frames_to_disk(video_path, slug)
        else:
            status_placeholder.warning("영상을 입력하거나 기존 영상을 선택해주세요.")
            st.stop()
    except Exception as e:
        status_placeholder.error(f"영상 준비 실패: {e}")
        st.stop()

    metadata = {
        "game_name": game_name,
        "genre": genre,
        "category": category_key,
        "publisher": (sel_existing.publisher if sel_existing else None),
    }

    # ── 같은 영상 검증 — 모든 옵션 (A/B/C) 에 매칭 카드 노출 후 분석 진행 차단 ─
    # 옵션 C: 시드 영상 직접 선택이므로 즉시 자기 자신과 매칭 (sim=1.0)
    # 옵션 A/B: 1) mp4 SHA-256 정확 매칭, 2) 메타 텍스트 임베딩 코사인 유사도
    # force_reanalyze 는 1회용 플래그 — 검증 시점에 즉시 pop 해서 무한 루프 방지.
    skip_check = st.session_state.get("force_reanalyze") == slug
    if skip_check:
        st.session_state.pop("force_reanalyze", None)

    matched_rec: Optional[VideoRecord] = None
    match_sim: float = 0.0
    match_reason: str = ""

    if not skip_check:
        if sel_existing is not None:
            # 옵션 C — 자기 자신이 매칭
            matched_rec = sel_existing
            match_sim = 1.0
            match_reason = "시드 영상 직접 선택"
        else:
            # 옵션 A/B — 해시 + 임베딩
            try:
                file_hash = sha256_file(video_path)
            except Exception as e:
                file_hash = None
                status_placeholder.warning(f"해시 계산 실패: {e}")

            if file_hash:
                hit = repo.find_by_hash(file_hash)
                if hit is not None:
                    matched_rec = hit
                    match_sim = 1.0
                    match_reason = "동일 파일 (SHA-256)"

            if matched_rec is None:
                try:
                    from openai import OpenAI
                    cat_ko = CATEGORY_KO.get(metadata["category"], metadata["category"])
                    query_text = f"{metadata['game_name']} | {metadata['genre']} | {cat_ko}"
                    client = OpenAI()
                    resp = client.embeddings.create(
                        model="text-embedding-3-small", input=query_text,
                    )
                    query_emb = list(resp.data[0].embedding)
                    hit2 = repo.find_similar_video(query_emb, threshold=0.95)
                    if hit2 is not None:
                        matched_rec, match_sim = hit2
                        match_reason = "메타 텍스트 임베딩 유사"
                except Exception as e:
                    status_placeholder.warning(f"임베딩 검증 실패 (계속 진행): {e}")

        if matched_rec is not None:
            # 매칭 결과를 session_state 에 보존 — 다음 rerun 에서 _render_pending_match() 가
            # ``start_clicked`` 분기 밖에서 카드 + 버튼을 그린다.
            st.session_state["pending_match"] = {
                "matched_slug": matched_rec.slug,
                "matched_game": matched_rec.game_name,
                "matched_category": matched_rec.category,
                "matched_genre": matched_rec.genre,
                "match_sim": float(match_sim),
                "match_reason": match_reason,
                "target_slug": slug,
            }
            st.rerun()

    # 검증 통과 또는 강제 재분석 — 원래 분석 흐름
    started_iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    status_placeholder.info(f"분석 시작 — {metadata['game_name']} ({metadata['genre']}, {CATEGORY_KO.get(metadata['category'])})")

    try:
        final_state, durations, total_elapsed = asyncio.run(
            _run_analysis_realtime(slug, video_path, metadata, progress_placeholder)
        )
    except Exception as e:
        status_placeholder.error(f"분석 실패: {type(e).__name__}: {e}")
        st.stop()

    # 결과 저장
    try:
        record = _state_to_record(slug, metadata, final_state, durations, total_elapsed, started_iso)
        # 다음 재분석 시 검증에 활용되도록 SHA-256 함께 보존 (force_reanalyze 분기 포함)
        try:
            record.file_hash = sha256_file(video_path)
        except Exception:
            pass
        repo.save_video(record)
        # 강제 재분석 플래그는 1회용 — 클리어
        st.session_state.pop("force_reanalyze", None)
    except Exception as e:
        status_placeholder.error(f"결과 저장 실패: {e}")
        st.stop()

    grade_ko = {"strong": "우수", "medium": "보통", "weak": "약함"}.get(record.grade or "", "—")
    total_str = f"{record.total_score:.2f}" if isinstance(record.total_score, (int, float)) else "—"
    status_placeholder.success(
        f"분석 완료! 등급: {grade_ko} · 합계: {total_str} · 소요 {total_elapsed:.1f}초 — 잠시 후 영상 상세로 이동합니다…"
    )
    # Streamlit 1.56 의 ``st.switch_page`` 는 query_params 를 새 페이지에 전달하지 않는
    # 케이스가 있어, session_state 를 fallback 채널로 함께 사용한다 (페이지 2에서 둘 다 시도).
    st.session_state["nav_slug"] = slug
    st.query_params["slug"] = slug
    time.sleep(2)
    st.switch_page("pages/2_detail.py")
else:
    # 클릭 전: 빈 상태 진행 카드 1회 렌더
    _render_progress(
        progress_placeholder,
        {n: "pending" for n in ALL_NODES},
        {},
    )
