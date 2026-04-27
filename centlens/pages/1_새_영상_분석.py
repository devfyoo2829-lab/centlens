"""페이지 1: 새 영상 분석 — 영상 입력 + 메타데이터 + 분석 진행 (mock).

이번 단계에서는 실제 LangGraph 호출 없이 mock 진행 상황만 표시한다.
실제 그래프 실행은 다음 단계에서 추가된다.
"""

import sys
from pathlib import Path

import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from centlens.ui.styles import (  # noqa: E402
    CATEGORY_KO,
    configure_page,
    render_header,
    tip_html,
)


configure_page(page_title="CentLens · 새 영상 분석")
render_header(active="upload")


# ─── 페이지 타이틀 ────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="margin-bottom:24px;">
      <h1>새 영상 분석</h1>
      <p style="font-size:14px; color:#a1a1aa; margin:0;">
        광고 영상 1편을 슈퍼센트 6축 프레임으로 자동 분해합니다. 약 30~40초 소요됩니다.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ─── 2 컬럼: 영상 입력 / 분류·메타 ───────────────────────────────────────────
col_video, col_meta = st.columns(2)

with col_video:
    st.markdown(
        '<div class="cl-card">'
        '<div class="cl-card-head">영상 입력</div>',
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader(
        "MP4 / 최대 100MB",
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
    st.markdown("</div>", unsafe_allow_html=True)

with col_meta:
    st.markdown(
        '<div class="cl-card">'
        '<div class="cl-card-head">분류 및 메타데이터</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="display:flex; align-items:center; margin: 0 0 6px;">'
        f'<label style="font-size:12px; color:#71717a;">분류</label>'
        f'{tip_html("분류는 왜 중요한가요?", "나중에 자사·경쟁사·시장 트렌드를 비교 분석할 때 기준이 돼요. 의미 검색에서도 분류로 필터링할 수 있어요.")}'
        "</div>",
        unsafe_allow_html=True,
    )
    category_key = st.segmented_control(
        "분류",
        options=list(CATEGORY_KO.keys()),
        format_func=lambda c: CATEGORY_KO.get(c, c),
        default="new",
        label_visibility="collapsed",
        key="upload_category",
    )

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
    use_container_width=True,
    key="start_analysis",
)

if start_clicked:
    if not uploaded and not youtube_url:
        st.warning("영상 파일을 업로드하거나 YouTube URL을 입력해주세요.")
    elif not game_name or not genre:
        st.warning("게임명과 장르를 입력해주세요.")
    else:
        # mock — 다음 단계에서 LangGraph astream 으로 교체
        st.session_state["mock_progress"] = "running"
        st.toast("분석을 시작합니다 (현재는 mock 진행)", icon="✓")


# ─── 분석 진행 상황 (mock) ───────────────────────────────────────────────────
def _step_row(state: str, label: str, sublabel: str = "", duration: str = "",
              tip_t: str = "", tip_b: str = "") -> str:
    """state: 'done' | 'running' | 'pending'."""
    if state == "done":
        icon = '<div style="width:16px; height:16px; background:#00d68f; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:10px; color:#000;">✓</div>'
        text_color = "#fff"
    elif state == "running":
        icon = '<div style="width:14px; height:14px; border:1.5px solid #f5a524; border-top-color:transparent; border-radius:50%;"></div>'
        text_color = "#fff"
    else:  # pending
        icon = '<div style="width:16px; height:16px; border:0.5px solid #404040; border-radius:50%;"></div>'
        text_color = "#a1a1aa"

    tip_inline = tip_html(tip_t, tip_b) if tip_t else ""
    duration_html = (
        f'<span style="font-size:12px; color:#71717a; font-family:&quot;JetBrains Mono&quot;, monospace;">{duration}</span>'
        if duration else
        f'<span style="font-size:12px; color:#71717a;">{sublabel or "대기"}</span>'
    )
    return (
        f'<div style="display:flex; align-items:center; gap:12px; padding:8px 12px; background:#000; border-radius:6px; border:0.5px solid #262626;">'
        f"{icon}"
        f'<div style="flex:1; display:flex; align-items:center;">'
        f'<span style="font-size:13px; color:{text_color};">{label}</span>'
        f"{tip_inline}"
        "</div>"
        f"{duration_html}"
        "</div>"
    )


def _axis_chip(state: str, name: str) -> str:
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
        f'<div><div style="font-size:11px; color:#fff;">{name}</div></div>'
        "</div>"
    )


progress = st.session_state.get("mock_progress", "idle")  # idle | running | done

# 시연용 mock 시나리오: 영상 준비 ✓ / 6축 5/6 진행 / 검증·등급·인덱싱 대기
if progress == "running":
    prep_state = "done"
    axis_states = ["done", "done", "done", "done", "done", "running"]
    cross_state = "pending"
    grade_state = "pending"
    embed_state = "pending"
    completed = 1 + sum(1 for s in axis_states if s == "done") + 0 + 0 + 0
elif progress == "done":
    prep_state = "done"
    axis_states = ["done"] * 6
    cross_state = "done"
    grade_state = "done"
    embed_state = "done"
    completed = 10
else:
    prep_state = "pending"
    axis_states = ["pending"] * 6
    cross_state = "pending"
    grade_state = "pending"
    embed_state = "pending"
    completed = 0

axes = [
    ("움직임", "변화 3축"),
    ("성장", "변화 3축"),
    ("확장", "변화 3축"),
    ("카메라", "연출 3축"),
    ("컬러", "연출 3축"),
    ("사운드", "연출 3축"),
]
axis_chips_html = "".join(
    _axis_chip(state, name) for state, (name, _) in zip(axis_states, axes)
)

axis_done_count = sum(1 for s in axis_states if s == "done")

steps_html = [
    _step_row(
        prep_state, "영상 준비",
        duration="3.2초" if prep_state == "done" else "",
        tip_t="영상 준비 단계",
        tip_b="영상에서 5장면(0%/5%/25%/50%/95% 지점)을 추출하고, 음성을 텍스트로 변환해요. AI가 영상 내용을 이해하기 위한 사전 작업입니다.",
    ),
    # 6축 그리드 박스
    f"""
    <div style="padding:12px; background:#000; border-radius:6px; border:0.5px solid #262626;">
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
        <div style="display:flex; align-items:center;">
          <span class="cl-label-upper" style="color:#71717a;">6축 평가 (병렬 실행 {'중' if 'running' in axis_states else '완료'})</span>
          {tip_html("6축이 뭔가요?", "슈퍼센트 자체 평가 프레임이에요. 변화 3축(움직임·성장·확장)은 시선을 끄는 요소를, 연출 3축(카메라·컬러·사운드)은 메시지 전달을 평가합니다.")}
        </div>
        <span style="font-size:11px; color:#71717a;">{axis_done_count} / 6 완료</span>
      </div>
      <p style="font-size:11px; color:#71717a; margin: 0 0 10px;">변화 3축과 연출 3축을 동시에 평가합니다.</p>
      <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:6px;">{axis_chips_html}</div>
    </div>
    """,
    _step_row(
        cross_state, "교차 검증",
        tip_t="교차 검증이 뭔가요?",
        tip_b="같은 영상을 6축을 한꺼번에, 다른 순서로 다시 평가해요. 1차 평가의 점수 편향을 줄이는 역할입니다. 두 결과를 비교해서 점수 차이가 큰 축을 찾아냅니다.",
    ),
    _step_row(
        grade_state, "등급 산출",
        tip_t="등급은 어떻게 결정되나요?",
        tip_b="6축 모두 4점 이상이면 우수, 3점 이상이면 보통, 그 외는 약함이에요. 한 축이라도 약하면 전체 등급이 낮아져요 (가장 약한 축이 기준).",
    ),
    _step_row(
        embed_state, "검색 인덱싱",
        tip_t="검색 인덱싱이 뭔가요?",
        tip_b="나중에 \"사운드가 약한 영상\" 같은 자연스러운 표현으로 비슷한 영상을 찾을 수 있도록, 영상 내용을 의미 기반으로 정리해두는 단계예요.",
    ),
]

st.markdown(
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
        {''.join(steps_html)}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if progress == "running":
    st.info(
        "이번 단계는 mock 진행입니다. 실제 LangGraph 분석은 다음 단계에서 연결됩니다. "
        "현재 분석된 5편 영상은 [분석한 영상 모음](/3_분석한_영상_모음)에서 확인할 수 있습니다."
    )
