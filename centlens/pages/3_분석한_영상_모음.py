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
    search_clicked = st.button("찾기", use_container_width=True, key="search_btn")

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


# ─── 필터 (분류/등급/장르) + 정렬 ────────────────────────────────────────────
genres_present = sorted({r.genre for r in records if r.genre})
filter_cols = st.columns([1, 1, 1, 5])
with filter_cols[0]:
    sel_categories = st.multiselect(
        "분류",
        options=list(CATEGORY_KO.keys()),
        format_func=lambda c: CATEGORY_KO.get(c, c),
        default=[],
        key="filter_category",
    )
with filter_cols[1]:
    sel_grades = st.multiselect(
        "등급",
        options=list(GRADE_KO.keys()),
        format_func=lambda g: GRADE_KO.get(g, g),
        default=[],
        key="filter_grade",
    )
with filter_cols[2]:
    sel_genres = st.multiselect(
        "장르",
        options=genres_present,
        default=[],
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
