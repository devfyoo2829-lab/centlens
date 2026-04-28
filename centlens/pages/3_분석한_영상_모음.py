"""페이지 3: 분석한 영상 모음 — 통계 + 의미 검색 + 카드 그리드."""

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
    AXIS_GROUP_COLOR,
    AXIS_KO,
    CATEGORY_KO,
    GRADE_COLORS,
    GRADE_KO,
    category_badge_html,
    configure_page,
    grade_badge_html,
    mini_chart_html,
    render_header,
    tip_html,
)


# ─── 페이지 설정 ──────────────────────────────────────────────────────────────
configure_page(page_title="CentLens · 분석한 영상 모음")
render_header(active="archive")


# ─── 데이터 로딩 ──────────────────────────────────────────────────────────────
repo = get_repository()
records: list[VideoRecord] = repo.list_videos()


def _final_score(rec: VideoRecord, axis: str) -> Optional[float]:
    triplet = rec.axis_scores.get(axis)
    if triplet is None or triplet.final is None:
        return None
    return triplet.final.get("score")


def _final_scores_dict(rec: VideoRecord) -> dict[str, Optional[float]]:
    return {ax: _final_score(rec, ax) for ax in AXES}


def _thumb_data_uri(slug: str) -> Optional[str]:
    """``data/frames/{slug}/0.jpg`` 를 data: URI로 변환. 없으면 None."""
    path = _PROJECT_ROOT / "data" / "frames" / slug / "0.jpg"
    if not path.is_file():
        return None
    try:
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return None


# ─── 페이지 타이틀 + 카운트 ──────────────────────────────────────────────────
n_total = len(records)
by_cat = {c: sum(1 for r in records if r.category == c) for c in ("new", "competitor", "trend")}
sub_parts = [f"지금까지 {n_total}편 분석"]
if by_cat["new"]:
    sub_parts.append(f"자사 신규 {by_cat['new']}편")
if by_cat["competitor"]:
    sub_parts.append(f"경쟁사 {by_cat['competitor']}편")
if by_cat["trend"]:
    sub_parts.append(f"시장 트렌드 {by_cat['trend']}편")

st.markdown(
    f"""
    <div style="margin-bottom: 24px;">
      <h1>분석한 영상 모음</h1>
      <p style="font-size:14px; color:#a1a1aa; margin:0;">{' · '.join(sub_parts)}</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ─── 통계 4카드 ───────────────────────────────────────────────────────────────
def _avg_axis_score(records: list[VideoRecord], axis: str) -> Optional[float]:
    vals = [s for s in (_final_score(r, axis) for r in records) if s is not None]
    return sum(vals) / len(vals) if vals else None


def _avg_total(records: list[VideoRecord]) -> Optional[float]:
    vals = [r.total_score for r in records if isinstance(r.total_score, (int, float))]
    return sum(vals) / len(vals) if vals else None


axis_avgs = {ax: _avg_axis_score(records, ax) for ax in AXES}
valid_axis_avgs = {ax: v for ax, v in axis_avgs.items() if v is not None}
best_axis = max(valid_axis_avgs, key=lambda k: valid_axis_avgs[k]) if valid_axis_avgs else None
worst_axis = min(valid_axis_avgs, key=lambda k: valid_axis_avgs[k]) if valid_axis_avgs else None
avg_total = _avg_total(records)

stat_cards: list[str] = []
stat_cards.append(
    '<div class="cl-stat">'
    '<div class="cl-stat-label"><span>전체 영상</span></div>'
    f'<div class="cl-stat-value">{n_total}</div>'
    "</div>"
)
stat_cards.append(
    '<div class="cl-stat">'
    f'<div class="cl-stat-label"><span>평균 총점</span>{tip_html("평균 총점", "분석한 영상들의 6축 점수 합계 평균이에요. 30점 만점 (각 축 5점 × 6축).")}</div>'
    f'<div class="cl-stat-value">{avg_total:.2f}</div>' if avg_total is not None else
    '<div class="cl-stat-value">—</div>'
)
stat_cards.append(
    '<div class="cl-stat-sub">30점 만점</div></div>'
    if avg_total is not None else "</div>"
)
# 위 두 청크는 평균 총점 카드 닫힘 — 깔끔하게 다시 작성
stat_cards = [
    '<div class="cl-stat">'
    '<div class="cl-stat-label"><span>전체 영상</span></div>'
    f'<div class="cl-stat-value">{n_total}</div>'
    "</div>",

    '<div class="cl-stat">'
    f'<div class="cl-stat-label"><span>평균 총점</span>'
    f'{tip_html("평균 총점", "분석한 영상들의 6축 점수 합계 평균이에요. 30점 만점 (각 축 5점 × 6축).")}'
    "</div>"
    + (
        f'<div class="cl-stat-value">{avg_total:.2f}</div><div class="cl-stat-sub">30점 만점</div>'
        if avg_total is not None
        else '<div class="cl-stat-value">—</div>'
    )
    + "</div>",
]

if best_axis is not None:
    color = AXIS_GROUP_COLOR.get("change") if best_axis in ("movement","growth","expansion") else AXIS_GROUP_COLOR.get("production")
    stat_cards.append(
        '<div class="cl-stat">'
        f'<div class="cl-stat-label"><span>가장 잘된 축 평균</span>'
        f'{tip_html("가장 잘된 축 평균", "6축 중 평균 점수가 가장 높은 축이에요. 우리가 분석한 영상들이 어떤 측면에서 강한지 알 수 있어요.")}'
        "</div>"
        f'<div class="cl-stat-value" style="color:{color};">{valid_axis_avgs[best_axis]:.2f}</div>'
        f'<div class="cl-stat-sub">{AXIS_KO[best_axis]}</div>'
        "</div>"
    )
else:
    stat_cards.append('<div class="cl-stat"><div class="cl-stat-label">가장 잘된 축 평균</div><div class="cl-stat-value">—</div></div>')

if worst_axis is not None:
    color = AXIS_GROUP_COLOR.get("change") if worst_axis in ("movement","growth","expansion") else AXIS_GROUP_COLOR.get("production")
    stat_cards.append(
        '<div class="cl-stat">'
        f'<div class="cl-stat-label"><span>가장 약한 축 평균</span>'
        f'{tip_html("가장 약한 축 평균", "6축 중 평균 점수가 가장 낮은 축이에요. 다음 광고 제작 시 보완이 필요한 영역을 알려줍니다.")}'
        "</div>"
        f'<div class="cl-stat-value" style="color:{color};">{valid_axis_avgs[worst_axis]:.2f}</div>'
        f'<div class="cl-stat-sub">{AXIS_KO[worst_axis]}</div>'
        "</div>"
    )
else:
    stat_cards.append('<div class="cl-stat"><div class="cl-stat-label">가장 약한 축 평균</div><div class="cl-stat-value">—</div></div>')

st.markdown(
    f'<div class="cl-stat-grid">{"".join(stat_cards)}</div>',
    unsafe_allow_html=True,
)


# ─── 의미 검색 (mock) ─────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="cl-card">
      <div style="display:flex; align-items:center; margin-bottom:4px;">
        <span style="font-size:13px; font-weight:500; color:#fff;">의미로 영상 찾기</span>
        {tip_html("의미로 영상 찾기", "키워드가 아닌 의미로 검색해요. 영상의 평가 내용을 AI가 이해해서, 입력하신 표현과 가장 가까운 영상을 찾아줍니다.")}
      </div>
      <p style="font-size:11px; color:#71717a; margin:0 0 12px;">
        자연스러운 표현으로 검색해보세요. AI가 의미를 이해해서 가장 가까운 영상을 찾아줍니다.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

if "search_query" not in st.session_state:
    st.session_state.search_query = ""

# 예시 칩 — 클릭 시 search_query 세팅
example_queries = (
    "사운드가 약했던 경쟁사 영상",
    "움직임이 강한 자사 영상",
    "캐릭터 변화가 있는 영상",
)
search_cols = st.columns([5, 1])
with search_cols[0]:
    query_input = st.text_input(
        "search_query_input",
        value=st.session_state.search_query,
        placeholder="확장 축이 강한 시뮬레이션 게임 영상",
        label_visibility="collapsed",
        key="search_query_textbox",
    )
with search_cols[1]:
    search_clicked = st.button("찾기", type="primary", use_container_width=True, key="search_btn")

# 칩 row
chip_cols = st.columns([1, 2, 2, 2, 5])
chip_cols[0].markdown(
    '<div style="font-size:11px; color:#71717a; padding-top:6px;">예시:</div>',
    unsafe_allow_html=True,
)
for i, q in enumerate(example_queries):
    if chip_cols[i + 1].button(q, key=f"chip_{i}", use_container_width=True):
        st.session_state.search_query = q
        st.rerun()

if search_clicked:
    st.session_state.search_query = query_input

active_query = st.session_state.search_query


# ─── 5편 6축 레이더 비교 ──────────────────────────────────────────────────────
import plotly.graph_objects as go  # noqa: E402

# 카테고리별 색상 팔레트 (자사=라벤더 3종, 경쟁사=민트 2종)
_NEW_PALETTE = ("#a78bfa", "#c4b5fd", "#7c3aed")
_COMP_PALETTE = ("#34d399", "#6ee7b7")
_TREND_PALETTE = ("#f5a524",)


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha:.2f})"


def _radar_color_for(rec: VideoRecord, idx_in_cat: int) -> str:
    if rec.category == "new":
        return _NEW_PALETTE[idx_in_cat % len(_NEW_PALETTE)]
    if rec.category == "competitor":
        return _COMP_PALETTE[idx_in_cat % len(_COMP_PALETTE)]
    return _TREND_PALETTE[idx_in_cat % len(_TREND_PALETTE)]


radar_records = list(records)
radar_records.sort(key=lambda r: ({"new": 0, "competitor": 1, "trend": 2}.get(r.category, 3), r.game_name))

axis_labels_ko = [AXIS_KO[ax] for ax in AXES]
axis_labels_loop = axis_labels_ko + [axis_labels_ko[0]]

fig = go.Figure()
cat_idx_counter = {"new": 0, "competitor": 0, "trend": 0}
for rec in radar_records:
    scores = [_final_score(rec, ax) or 0.0 for ax in AXES]
    scores_loop = scores + [scores[0]]
    color = _radar_color_for(rec, cat_idx_counter[rec.category])
    cat_idx_counter[rec.category] += 1

    fig.add_trace(go.Scatterpolar(
        r=scores_loop,
        theta=axis_labels_loop,
        name=rec.game_name,
        mode="lines+markers",
        line=dict(color=color, width=2),
        marker=dict(size=5, color=color),
        fill="toself",
        fillcolor=_hex_to_rgba(color, 0.15),
        legendgroup=rec.category,
        legendgrouptitle_text=CATEGORY_KO.get(rec.category, rec.category),
    ))

fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Pretendard, Inter, sans-serif", color="#d4d4d8", size=12),
    polar=dict(
        bgcolor="rgba(0,0,0,0)",
        radialaxis=dict(
            range=[0, 5],
            tickvals=[1, 2, 3, 4, 5],
            tickfont=dict(family="JetBrains Mono, monospace", size=10, color="#71717a"),
            gridcolor="#262626",
            linecolor="#404040",
            tickcolor="#404040",
            angle=90,
            tickangle=90,
        ),
        angularaxis=dict(
            tickfont=dict(family="Pretendard, Inter, sans-serif", size=12, color="#d4d4d8"),
            gridcolor="#262626",
            linecolor="#262626",
        ),
    ),
    legend=dict(
        font=dict(family="Pretendard, Inter, sans-serif", size=11, color="#d4d4d8"),
        bgcolor="rgba(0,0,0,0)",
        bordercolor="rgba(0,0,0,0)",
        groupclick="toggleitem",
        itemsizing="constant",
        x=1.02, y=1.0,
        xanchor="left", yanchor="top",
    ),
    margin=dict(t=20, b=10, l=20, r=20),
    height=420,
    showlegend=True,
)


# ── 동적 인사이트 계산 ────────────────────────────────────────────────────────
def _avg(lst: list[float]) -> Optional[float]:
    vals = [v for v in lst if isinstance(v, (int, float))]
    return sum(vals) / len(vals) if vals else None


def _avg_axis(records: list[VideoRecord], axis: str) -> Optional[float]:
    return _avg([_final_score(r, axis) or 0.0 for r in records if _final_score(r, axis) is not None])


axis_avgs_all = {ax: _avg_axis(radar_records, ax) for ax in AXES}
valid_avgs = {ax: v for ax, v in axis_avgs_all.items() if v is not None}
worst_ax = min(valid_avgs, key=lambda k: valid_avgs[k]) if valid_avgs else None
best_ax = max(valid_avgs, key=lambda k: valid_avgs[k]) if valid_avgs else None

new_records = [r for r in radar_records if r.category == "new"]
comp_records = [r for r in radar_records if r.category == "competitor"]


def _gap_axis(new_rs: list[VideoRecord], comp_rs: list[VideoRecord]) -> Optional[tuple[str, float]]:
    """자사 vs 경쟁사 평균 점수 차이가 가장 큰 축 (절댓값)."""
    if not new_rs or not comp_rs:
        return None
    best: Optional[tuple[str, float]] = None
    for ax in AXES:
        an = _avg_axis(new_rs, ax)
        ac = _avg_axis(comp_rs, ax)
        if an is None or ac is None:
            continue
        diff = an - ac
        if best is None or abs(diff) > abs(best[1]):
            best = (ax, diff)
    return best


gap = _gap_axis(new_records, comp_records)


def _category_summary() -> str:
    parts: list[str] = []
    if new_records:
        parts.append(f"자사 {len(new_records)}편")
    if comp_records:
        parts.append(f"경쟁사 {len(comp_records)}편")
    return " vs ".join(parts) if parts else f"전체 {len(radar_records)}편"


insight_lines: list[str] = []
if worst_ax and valid_avgs[worst_ax] is not None:
    insight_lines.append(
        f'<li>전체 <strong style="color:#fff;">{AXIS_KO[worst_ax]}</strong> 축 평균 '
        f'<span class="cl-num" style="color:#fff;">{valid_avgs[worst_ax]:.2f}</span>점 — '
        f'5편 공통 약점</li>'
    )
if best_ax and valid_avgs[best_ax] is not None:
    insight_lines.append(
        f'<li>전체 <strong style="color:#fff;">{AXIS_KO[best_ax]}</strong> 축 평균 '
        f'<span class="cl-num" style="color:#fff;">{valid_avgs[best_ax]:.2f}</span>점 — 가장 강한 축</li>'
    )
if gap is not None:
    ax_g, diff_g = gap
    direction = "강함" if diff_g > 0 else "약함"
    insight_lines.append(
        f'<li>자사가 <strong style="color:#fff;">{AXIS_KO[ax_g]}</strong> 축에서 '
        f'경쟁사 대비 <span class="cl-num" style="color:#fff;">{diff_g:+.2f}</span>점 {direction}</li>'
    )
insight_html = "<ul style='margin: 8px 0 0 0; padding-left: 18px; line-height:1.8; font-size:13px; color:#a1a1aa;'>" + "".join(insight_lines) + "</ul>"

# ── 차트 카드 렌더 ───────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="cl-card" style="margin-bottom:24px;">
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
        <div style="display:flex; align-items:center;">
          <span style="font-size:13px; font-weight:500; color:#fff;">5편 6축 비교</span>
          {tip_html("5편 6축 비교", "분석된 5편의 final 점수를 6각형 레이더로 겹쳐 비교합니다. 자사 신규는 라벤더, 경쟁사는 민트 계열로 구분돼요. legend를 클릭해 영상별로 켜고 끌 수 있어요.")}
        </div>
        <span style="font-size:11px; color:#71717a;">5점 만점 · {_category_summary()}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
radar_left, radar_right = st.columns([3, 2])
with radar_left:
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
with radar_right:
    st.markdown(
        f"""
        <div style="padding: 24px 0 0 8px;">
          <div style="font-size:11px; color:#71717a; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px;">핵심 인사이트</div>
          {insight_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── 필터 (분류/등급/장르) + 정렬 ────────────────────────────────────────────
genres_present = sorted({r.genre for r in records if r.genre})
filter_cols = st.columns([1, 1, 1, 5])
with filter_cols[0]:
    sel_categories = st.multiselect(
        "분류",
        options=list(CATEGORY_KO.keys()),
        format_func=lambda c: CATEGORY_KO.get(c, c),
        default=[],
        placeholder="전체",
        key="filter_category",
    )
with filter_cols[1]:
    sel_grades = st.multiselect(
        "등급",
        options=list(GRADE_KO.keys()),
        format_func=lambda g: GRADE_KO.get(g, g),
        default=[],
        placeholder="전체",
        key="filter_grade",
    )
with filter_cols[2]:
    sel_genres = st.multiselect(
        "장르",
        options=genres_present,
        default=[],
        placeholder="전체",
        key="filter_genre",
    )


# ─── 정렬 / 검색 mock 적용 ──────────────────────────────────────────────────
def _mock_search_sort(records: list[VideoRecord], query: str) -> list[VideoRecord]:
    q = (query or "").lower()
    if any(k in q for k in ("사운드", "음향", "소리", "sound")):
        # weakest_axis가 sound인 영상 우선, 그 다음 sound final 점수 오름차순
        return sorted(
            records,
            key=lambda r: (
                0 if r.weakest_axis == "sound" else 1,
                _final_score(r, "sound") if _final_score(r, "sound") is not None else 99,
            ),
        )
    if any(k in q for k in ("성장", "캐릭터", "growth")):
        return sorted(
            records,
            key=lambda r: (
                0 if r.weakest_axis == "growth" else 1,
                _final_score(r, "growth") if _final_score(r, "growth") is not None else 99,
            ),
        )
    if any(k in q for k in ("확장", "공간", "expansion")):
        return sorted(
            records,
            key=lambda r: _final_score(r, "expansion") if _final_score(r, "expansion") is not None else 99,
        )
    if any(k in q for k in ("움직임", "쏟아", "튕", "movement")):
        return sorted(
            records,
            key=lambda r: -(_final_score(r, "movement") or 0),
        )
    # 기본: 총점 내림차순
    return sorted(
        records,
        key=lambda r: -(r.total_score if isinstance(r.total_score, (int, float)) else 0),
    )


def _apply_filters(records: list[VideoRecord]) -> list[VideoRecord]:
    out = records
    if sel_categories:
        out = [r for r in out if r.category in sel_categories]
    if sel_grades:
        out = [r for r in out if r.grade in sel_grades]
    if sel_genres:
        out = [r for r in out if r.genre in sel_genres]
    return out


sorted_records = _mock_search_sort(_apply_filters(records), active_query)

if active_query:
    st.markdown(
        f'<div style="font-size:11px; color:#71717a; margin: 8px 0 12px;">'
        f'검색어 “{active_query}” · 결과 {len(sorted_records)}편 (의미 매칭, mock)</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f'<div style="font-size:11px; color:#71717a; margin: 8px 0 12px;">'
        f'정렬: 총점 내림차순 · 표시 {len(sorted_records)}편</div>',
        unsafe_allow_html=True,
    )


# ─── 카드 그리드 (2 컬럼) ────────────────────────────────────────────────────
def _render_card(rec: VideoRecord) -> None:
    final_scores = _final_scores_dict(rec)
    grade = grade_badge_html(rec.grade)
    cat_badge = category_badge_html(rec.category)

    thumb_uri = _thumb_data_uri(rec.slug)
    if thumb_uri:
        thumb_html = (
            '<div class="cl-archive-thumb">'
            f'<img class="cl-archive-thumb-img" src="{thumb_uri}" alt="{rec.game_name}" />'
            "</div>"
        )
    else:
        thumb_html = (
            '<div class="cl-archive-thumb">'
            '<div class="cl-archive-thumb-empty">썸네일 없음</div>'
            "</div>"
        )

    total_str = f"{rec.total_score:.2f}" if isinstance(rec.total_score, (int, float)) else "—"
    weakest_str = AXIS_KO.get(rec.weakest_axis or "", "—")
    publisher = rec.publisher or "—"

    st.markdown(
        f"""
        <div class="cl-archive-card">
          <div class="cl-archive-card-head">
            <div style="display:flex; align-items:center; gap:8px;">
              {cat_badge}
              <span style="font-size:13px; font-weight:500; color:#fff;">{rec.game_name}</span>
            </div>
            {grade}
          </div>
          {thumb_html}
          <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
            <span style="font-size:11px; color:#71717a;">총점</span>
            <span class="cl-num" style="font-size:14px;">{total_str}</span>
          </div>
          <div style="display:flex; align-items:center; margin: 0 0 6px;">
            <span style="font-size:10px; color:#71717a;">변화 3축 · 연출 3축 점수</span>
            {tip_html("6축 미니 차트", "왼쪽부터 움직임·성장·확장(라벤더, 변화 3축), 카메라·컬러·사운드(민트, 연출 3축) 순이에요. 막대 길이가 점수예요.")}
          </div>
          {mini_chart_html(final_scores)}
          <div style="display:flex; align-items:center; justify-content:space-between; margin-top:10px;">
            <span style="font-size:10px; color:#71717a;">가장 약한 축: {weakest_str}</span>
            <span style="font-size:10px; color:#71717a;">{rec.genre} · {publisher}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("자세히 보기", key=f"open_{rec.slug}", use_container_width=True):
        st.query_params["slug"] = rec.slug
        st.switch_page("pages/2_영상_상세.py")


grid_cols = st.columns(2)
for idx, rec in enumerate(sorted_records):
    with grid_cols[idx % 2]:
        _render_card(rec)
