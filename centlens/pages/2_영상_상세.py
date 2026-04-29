"""페이지 2: 영상 상세 — 6축 게이지 + A/B 관점 차이 카드 + 단계별 시간 + 마케터 코멘트.

URL 쿼리 ``?slug=...`` 로 영상 식별.
"""

import base64
import sys
from pathlib import Path
from typing import Optional

import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from centlens.core.repository import VideoRecord, get_repository  # noqa: E402
from centlens.ui.styles import (  # noqa: E402
    AXES,
    AXIS_KO,
    CATEGORY_KO,
    axis_gauge_html,
    category_badge_html,
    configure_page,
    fallback_box_html,
    grade_badge_html,
    render_header,
    tip_html,
)


# ─── 페이지 설정 ──────────────────────────────────────────────────────────────
configure_page(page_title="영상 상세 · CentLens")
render_header(active="detail")


# ─── slug 검증 ────────────────────────────────────────────────────────────────
# Streamlit 1.56 ``st.switch_page`` 는 query_params 를 새 페이지에 전달하지 않을 수 있어
# session_state(``nav_slug``)을 fallback 채널로 사용한다. 둘 다 비어있을 때만 fallback 화면.
slug = st.query_params.get("slug") or st.session_state.get("nav_slug")
if slug and not st.query_params.get("slug"):
    # session_state로 들어온 경우 query_params 도 동기화 (URL 공유 가능하게)
    st.query_params["slug"] = slug
if not slug:
    st.markdown(
        """
        <div class="cl-empty-state">
          <h3>영상이 선택되지 않았습니다</h3>
          <p>새 영상 분석을 시작하거나, 분석한 영상 모음에서 자세히 보기를 클릭하면<br>
          6축 평가 결과를 확인할 수 있습니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    empty_cols = st.columns(2)
    if empty_cols[0].button("새 영상 분석", type="primary", use_container_width=True,
                             key="empty_to_upload"):
        st.switch_page("pages/1_새_영상_분석.py")
    if empty_cols[1].button("분석한 영상 모음", use_container_width=True,
                             key="empty_to_archive"):
        st.switch_page("pages/3_분석한_영상_모음.py")
    st.stop()

repo = get_repository()
rec: Optional[VideoRecord] = repo.get_video(slug)
if rec is None:
    st.markdown(
        f"""
        <div class="cl-fallback" style="margin-top:24px;">
          slug “{slug}” 에 해당하는 영상을 찾을 수 없습니다.<br>
          <a href="/분석한_영상_모음" target="_self" style="color:#0070f3;">분석한 영상 모음 →</a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()


# ─── 데이터 추출 ──────────────────────────────────────────────────────────────
def _score(triplet_attr: Optional[dict]) -> Optional[float]:
    if not triplet_attr:
        return None
    return triplet_attr.get("score")


def _rationale(triplet_attr: Optional[dict]) -> str:
    if not triplet_attr:
        return ""
    return triplet_attr.get("rationale") or ""


axis_data: dict[str, dict] = {}
for ax in AXES:
    triplet = rec.axis_scores.get(ax)
    a = triplet.a if triplet else None
    b = triplet.b if triplet else None
    f = triplet.final if triplet else None
    diff = None
    if a and b and a.get("score") is not None and b.get("score") is not None:
        diff = abs(float(a["score"]) - float(b["score"]))
    axis_data[ax] = {
        "a": a, "b": b, "final": f,
        "a_score": _score(a),
        "b_score": _score(b),
        "final_score": _score(f),
        "diff": diff,
    }


# ─── 뒤로가기 ─────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="margin-bottom:8px;">'
    '<a href="/분석한_영상_모음" target="_self" style="font-size:12px; color:#a1a1aa; font-weight:500;">'
    "분석한 영상 모음 →</a>"
    "</div>",
    unsafe_allow_html=True,
)


# ─── 헤더 (게임명 + 메타 + 종합 등급) ────────────────────────────────────────
publisher = rec.publisher or "—"
date_part = (rec.started_at or "")[:10] if rec.started_at else ""
date_text = f" · {date_part} 분석" if date_part else ""
total_str = f"{rec.total_score:.2f}" if isinstance(rec.total_score, (int, float)) else "—"

st.markdown(
    f"""
    <div style="display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:24px;">
      <div>
        <h1>{rec.game_name}</h1>
        <div style="display:flex; align-items:center; gap:8px;">
          {category_badge_html(rec.category)}
          <span style="font-size:12px; color:#71717a;">{rec.genre} · {publisher}{date_text}</span>
        </div>
      </div>
      <div style="text-align:right;">
        <div style="display:flex; align-items:center; justify-content:flex-end; margin-bottom:4px;">
          <span style="font-size:11px; color:#71717a;">종합 등급</span>
          {tip_html("등급 기준", "6축 모두 4점 이상이면 <strong>우수</strong>, 3점 이상이면 <strong>보통</strong>, 그 외는 <strong>약함</strong>. 가장 약한 축이 전체 등급을 결정해요.")}
        </div>
        <div style="display:flex; align-items:center; gap:8px; justify-content:flex-end;">
          {grade_badge_html(rec.grade)}
          <span class="cl-num" style="font-size:18px; color:#fff;">{total_str}</span>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ─── 영상 + 추출 5장면 ───────────────────────────────────────────────────────
def _video_path(slug: str) -> Optional[Path]:
    p = _PROJECT_ROOT / "data" / "videos" / f"{slug}.mp4"
    return p if p.is_file() else None


def _frame_data_uri(slug: str, idx: int) -> Optional[str]:
    p = _PROJECT_ROOT / "data" / "frames" / slug / f"{idx}.jpg"
    if not p.is_file():
        return None
    try:
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return None


video_path = _video_path(rec.slug)
frame_uris = [_frame_data_uri(rec.slug, i) for i in range(5)]

st.markdown(
    f"""
    <div class="cl-card" style="display:flex; align-items:center; gap:16px;">
      <div style="width: 220px; flex-shrink:0;" id="cl-video-slot"></div>
      <div style="flex:1;">
        <div style="display:flex; align-items:center; margin-bottom:2px;">
          <span style="font-size:12px; color:#a1a1aa;">영상에서 추출한 5장면</span>
          {tip_html("왜 5장면만?", "영상의 시작·초반·중반·후반·종료 시점에서 한 장씩 골라 AI에게 보여줘요. 핵심 장면이 균등히 포함되도록 0%, 5%, 25%, 50%, 95% 지점에서 추출합니다.")}
        </div>
        <div style="display:grid; grid-template-columns: repeat(5, 1fr); gap:6px; margin-top:8px;">
          {''.join(
              f'<div class="cl-frame-placeholder" style="background-image:url(\'{uri}\'); background-size:cover; background-position:center;"></div>'
              if uri else
              '<div class="cl-frame-placeholder">프레임 없음</div>'
              for uri in frame_uris
          )}
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 영상 플레이어 — fallback 처리
if video_path:
    with st.container():
        st.video(str(video_path))
else:
    st.markdown(
        '<div class="cl-fallback" style="margin-bottom:24px;">'
        "영상 파일이 로드되지 않았습니다. (배포 환경에서는 별도 처리 필요)"
        "</div>",
        unsafe_allow_html=True,
    )


# ─── 6축 평가 헤더 + 가장 약한 축 ────────────────────────────────────────────
weakest_score = (
    axis_data[rec.weakest_axis]["final_score"]
    if rec.weakest_axis and rec.weakest_axis in axis_data
    else None
)
weakest_str = (
    f"{AXIS_KO[rec.weakest_axis]} · {weakest_score:.2f}점"
    if rec.weakest_axis and weakest_score is not None
    else "—"
)

st.markdown(
    f"""
    <div style="display:flex; align-items:flex-end; justify-content:space-between; margin: 8px 0 16px;">
      <div style="display:flex; align-items:center;">
        <h2 style="margin:0;">6축 평가</h2>
        {tip_html("6축이란?", "슈퍼센트 자체 평가 프레임이에요. <strong>변화 3축</strong>(움직임·성장·확장)은 시선을 끄는 요소를, <strong>연출 3축</strong>(카메라·컬러·사운드)은 메시지 전달을 평가합니다. 각 축을 1~5점으로 채점해요.")}
      </div>
      <div style="display:flex; align-items:center;">
        <span style="font-size:12px; color:#71717a;">가장 약한 축: <span style="color:#a1a1aa;">{weakest_str}</span></span>
        {tip_html("가장 약한 축", "6축 중 final 점수가 가장 낮은 축이에요. 이 축의 점수가 3점 미만이면 등급이 약함으로 떨어집니다.")}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ─── 변화 3축 카드 ───────────────────────────────────────────────────────────
def _build_axis_card(group_key: str, group_label: str, group_color: str,
                     axes: list[str], group_tip_title: str, group_tip_body: str,
                     subtitle: str) -> str:
    rows: list[str] = []
    axis_tips = {
        "movement": ("움직임", "유저의 시선을 잡는 시각적 변화. 절단·쏟아짐·튕김 같은 물리적 움직임이 강할수록 점수가 높아요. 햄버거가 우르르 쏟아지거나 유리병이 터지는 장면 같은 것."),
        "growth":   ("성장", "플레이어 캐릭터의 변화. 외형이 바뀌거나 능력치가 상승하는 장면이 명확할수록 점수가 높아요. 게이트를 통과하며 캐릭터가 커지거나 변신하는 연출 같은 것."),
        "expansion":("확장", "공간이 넓어지거나 시스템이 변화. 매장이 늘어나거나 새로운 기능이 추가되는 장면이 강할수록 점수가 높아요. 1층 매장이 2층 빌딩으로 확장되는 장면 같은 것."),
        "camera":   ("카메라", "시점·앵글·전환의 다양성. 탑뷰에서 측면뷰로 전환되거나, 카메라가 따라가며 정보를 추가로 보여주는 연출이 강할수록 점수가 높아요."),
        "color":    ("컬러", "색상 대비와 의미 전달. 핵심 오브젝트가 난색으로 시선을 끌고 배경이 차분한 톤으로 받쳐주는 식의 색상 활용이 강할수록 점수가 높아요."),
        "sound":    ("사운드", "나레이션·효과음·BGM의 활용도. 강조 구간에 효과음을 매칭하거나 나레이션 톤이 변화하며 몰입을 만드는 연출이 강할수록 점수가 높아요."),
    }
    for ax in axes:
        d = axis_data[ax]
        is_weakest = (rec.weakest_axis == ax)
        diverged = d["diff"] is not None and d["diff"] >= 1.0
        tip_t, tip_b = axis_tips[ax]
        rows.append(axis_gauge_html(
            ax,
            a_score=d["a_score"],
            b_score=d["b_score"],
            final_score=d["final_score"],
            is_weakest=is_weakest,
            diverged=diverged,
            tip_title=tip_t, tip_body=tip_b,
        ))
    return (
        '<div class="cl-card">'
        '<div style="margin-bottom:14px;">'
        '<div style="display:flex; align-items:center;">'
        f'<span class="cl-label-upper" style="color:{group_color};">{group_label}</span>'
        f'{tip_html(group_tip_title, group_tip_body)}'
        "</div>"
        f'<div style="font-size:11px; color:#71717a; margin-top:2px;">{subtitle}</div>'
        "</div>"
        f'<div>{"".join(rows)}</div>'
        "</div>"
    )


st.markdown(
    _build_axis_card(
        "change", "변화 3축", "#a78bfa",
        ["movement", "growth", "expansion"],
        "변화 3축",
        "유저의 시선을 끄는 변화 요소예요. 광고 영상에서 처음 3초 안에 시선을 잡으려면 강한 변화가 필요합니다.",
        "유저의 시선을 끄는 변화 — 움직임·성장·확장",
    ),
    unsafe_allow_html=True,
)
st.markdown(
    _build_axis_card(
        "production", "연출 3축", "#34d399",
        ["camera", "color", "sound"],
        "연출 3축",
        "정보 전달과 몰입을 만드는 연출 요소예요. 시선을 잡은 후 메시지를 효과적으로 전달하기 위해 필요합니다.",
        "정보 전달과 몰입을 만드는 연출 — 카메라·컬러·사운드",
    ),
    unsafe_allow_html=True,
)


# ─── 관점 차이 카드 (앰버 톤) — diff 가장 큰 축 자동 선정 ──────────────────
diverged_axes = [(ax, d["diff"]) for ax, d in axis_data.items() if d["diff"] is not None and d["diff"] >= 1.0]
if diverged_axes:
    top_ax, top_diff = max(diverged_axes, key=lambda t: t[1])
    d = axis_data[top_ax]
    a_rat = _rationale(d["a"])
    b_rat = _rationale(d["b"])
    a_str = f"{d['a_score']:.2f}" if d["a_score"] is not None else "—"
    b_str = f"{d['b_score']:.2f}" if d["b_score"] is not None else "—"

    st.markdown(
        f"""
        <div class="cl-divergence-card">
          <div class="cl-divergence-head">
            <div style="display:flex; align-items:center;">
              <span class="cl-divergence-title">{AXIS_KO[top_ax]} 축 — 두 가지 관점이 갈림</span>
              {tip_html("왜 두 점수가 다를까요?", "AI가 6축을 각각 따로 본 결과(1차)와 6축을 한꺼번에 다시 본 결과(검증)를 비교해요. 차이가 1점 이상이면 한 영상에 여러 해석이 가능하다는 신호예요. 마케터의 판단이 중요해지는 영역입니다.")}
            </div>
            <span class="cl-divergence-diff">점수 차이 {top_diff:.2f}</span>
          </div>
          <div class="cl-divergence-grid">
            <div class="cl-divergence-pane">
              <div class="cl-divergence-pane-head">
                <div style="display:flex; align-items:center;">
                  <span style="font-size:11px; color:#a1a1aa; font-weight:500;">1차 평가</span>
                  {tip_html("1차 평가", "6개 축을 각각 독립된 AI가 따로 평가했어요. 다른 축의 결과를 모르는 상태에서 자기 축만 봅니다.")}
                </div>
                <span class="cl-num" style="font-size:14px;">{a_str}</span>
              </div>
              <p class="cl-divergence-pane-rationale">{a_rat}</p>
            </div>
            <div class="cl-divergence-pane">
              <div class="cl-divergence-pane-head">
                <div style="display:flex; align-items:center;">
                  <span style="font-size:11px; color:#a1a1aa; font-weight:500;">교차 검증</span>
                  {tip_html("교차 검증", "같은 영상을 6축을 한꺼번에, 다른 순서로 다시 평가해요. 1차 평가의 점수 편향을 줄이는 역할입니다.")}
                </div>
                <span class="cl-num" style="font-size:14px;">{b_str}</span>
              </div>
              <p class="cl-divergence-pane-rationale">{b_rat}</p>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── 분석 단계별 시간 ────────────────────────────────────────────────────────
NODE_LABEL = {
    "preprocessor": "영상 준비",
    "movement_judge": "움직임 평가",
    "growth_judge": "성장 평가",
    "expansion_judge": "확장 평가",
    "camera_judge": "카메라 평가",
    "color_judge": "컬러 평가",
    "sound_judge": "사운드 평가",
    "cross_check": "교차 검증",
    "grade_calculator": "등급 산출",
    "embedder": "검색 인덱싱",
}
NODE_ORDER = (
    "preprocessor", "movement_judge", "growth_judge", "expansion_judge",
    "camera_judge", "color_judge", "sound_judge", "cross_check",
)
EMPHASIS_NODES = {"cross_check"}

durations = rec.durations_sec or {}
cells: list[str] = []
for node in NODE_ORDER:
    val = durations.get(node)
    val_str = f"{val:.1f}초" if isinstance(val, (int, float)) else "—"
    label = NODE_LABEL[node]
    emph = "cl-timing-cell-emph" if node in EMPHASIS_NODES else ""
    cells.append(
        f'<div class="cl-timing-cell {emph}">'
        f'<span class="cl-timing-label" style="{"color:#fff;" if node in EMPHASIS_NODES else ""}">{label}</span>'
        f'<span class="cl-timing-value" style="{"color:#fff;" if node in EMPHASIS_NODES else ""}">{val_str}</span>'
        "</div>"
    )

total_elapsed = rec.total_elapsed_sec
total_str_t = f"{total_elapsed:.2f}초" if isinstance(total_elapsed, (int, float)) else "—"

st.markdown(
    f"""
    <div class="cl-card">
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
        <div style="display:flex; align-items:center;">
          <span style="font-size:13px; font-weight:500; color:#fff;">분석 단계별 시간</span>
          {tip_html("분석 단계별 시간", "AI가 각 평가 단계를 처리한 시간이에요. 6개 축은 동시에(병렬) 진행되어, 한 번에 한 축씩 평가하는 것보다 빠릅니다.")}
        </div>
      </div>
      <div class="cl-timing-grid">{"".join(cells)}</div>
      <div style="margin-top:12px; padding-top:12px; border-top:0.5px solid #262626; display:flex; align-items:center; justify-content:space-between;">
        <span style="font-size:11px; color:#71717a;">총 처리 시간</span>
        <span class="cl-num" style="font-size:12px; color:#fff;">{total_str_t}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ─── 마케터 코멘트 ───────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="cl-card">
      <div style="display:flex; align-items:center; margin-bottom:4px;">
        <span class="cl-comment-head">마케터 코멘트</span>
        {tip_html("마케터 코멘트", "AI 평가와 다른 견해, 추가 인사이트가 있다면 기록해두세요. 나중에 영상을 다시 볼 때 의사결정 맥락이 됩니다.")}
      </div>
      <p class="cl-comment-hint">AI 평가와 다른 견해, 추가 인사이트가 있다면 기록해두세요.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
comment_key = f"comment_{rec.slug}"
if comment_key not in st.session_state:
    st.session_state[comment_key] = ""
st.text_area(
    "코멘트",
    placeholder="이 영상에 대한 의견...",
    key=comment_key,
    label_visibility="collapsed",
    height=120,
)
save_cols = st.columns([5, 1])
with save_cols[1]:
    if st.button("저장", type="primary", key=f"save_{rec.slug}", use_container_width=True):
        # 데모 단계에서는 session_state에만 보존. SupabaseRepository 단계에서 영구 저장 예정.
        st.toast("코멘트가 저장됐어요 (현재는 세션 임시 저장)", icon="✅")
