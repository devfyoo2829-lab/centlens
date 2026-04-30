"""페이지 3: 분석한 영상 모음 — 통계 + 의미 검색 + 카드 그리드."""

import base64
import sys
from pathlib import Path
from typing import Optional

import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import time  # noqa: E402

from centlens.core.repository import (  # noqa: E402
    JsonRepository,
    VideoRecord,
    get_repository,
)
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
configure_page(page_title="분석한 영상 모음 · CentLens")
render_header(active="archive")


# ─── 데이터 로딩 ──────────────────────────────────────────────────────────────
repo = get_repository()

# 페이지 진입 시 시드 자동 복원 (.deleted_seeds 등재된 slug는 제외)
if isinstance(repo, JsonRepository):
    try:
        _restored = repo.restore_missing_seeds()
        if _restored:
            st.toast(f"시드 영상 {len(_restored)}편 복원됨", icon="🌱")
    except Exception:
        pass  # 복원 실패해도 페이지 렌더는 계속

show_deleted = st.session_state.get("show_deleted", False)
records: list[VideoRecord] = repo.list_videos(include_deleted=False)
deleted_records: list[VideoRecord] = []
if show_deleted:
    deleted_records = [
        r for r in repo.list_videos(include_deleted=True) if r.deleted_at is not None
    ]


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

title_cols = st.columns([6, 1])
with title_cols[0]:
    st.markdown(
        f"""
        <div style="margin-bottom: 24px;">
          <h1>분석한 영상 모음</h1>
          <p style="font-size:14px; color:#a1a1aa; margin:0;">{' · '.join(sub_parts)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with title_cols[1]:
    st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)
    if st.button("시드 복원", key="restore_seeds_btn", help="삭제 기록을 비우고 시드 5편을 모두 복원"):
        if isinstance(repo, JsonRepository):
            repo.clear_deleted_seeds_log()
            restored = repo.restore_missing_seeds()
            st.toast(f"시드 {len(restored)}편 복원" if restored else "복원할 시드 없음", icon="🌱")
            time.sleep(0.5)
            st.rerun()

# 삭제된 영상 보기 토글
n_deleted_total = sum(
    1 for r in repo.list_videos(include_deleted=True) if r.deleted_at is not None
)
toggle_label = (
    f"삭제된 영상 보기 ({n_deleted_total}편)" if n_deleted_total else "삭제된 영상 보기"
)
new_toggle = st.toggle(
    toggle_label,
    value=show_deleted,
    key="show_deleted_toggle",
    help="휴지통에 있는 영상도 함께 표시합니다. 삭제된 카드는 회색 톤 + '복원' 버튼.",
)
if new_toggle != show_deleted:
    st.session_state["show_deleted"] = new_toggle
    st.rerun()

# 더미 markdown — 위 columns가 끝나면 다음 섹션이 자연스럽게 이어지도록.
st.markdown(
    """
    <div style="display:none;"></div>
    """,
    unsafe_allow_html=True,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 의미 검색 (페이지 상단) — 검색 활성 시 통계+6축+필터+그리드 모두 차단
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(show_spinner=False, ttl=600)
def _embed_query(text: str) -> Optional[list[float]]:
    """검색어를 OpenAI text-embedding-3-small 로 임베딩. 실패 시 None."""
    if not text.strip():
        return None
    try:
        from openai import OpenAI
        client = OpenAI()
        resp = client.embeddings.create(model="text-embedding-3-small", input=text)
        return list(resp.data[0].embedding)
    except Exception:
        return None


def _mock_search_sort(records: list[VideoRecord], query: str) -> list[VideoRecord]:
    """API 키 없을 때 fallback — 키워드 매칭 기반 정렬."""
    q = (query or "").lower()
    if any(k in q for k in ("사운드", "음향", "소리", "sound")):
        return sorted(records, key=lambda r: (
            0 if r.weakest_axis == "sound" else 1,
            _final_score(r, "sound") if _final_score(r, "sound") is not None else 99,
        ))
    if any(k in q for k in ("성장", "캐릭터", "growth")):
        return sorted(records, key=lambda r: (
            0 if r.weakest_axis == "growth" else 1,
            _final_score(r, "growth") if _final_score(r, "growth") is not None else 99,
        ))
    if any(k in q for k in ("확장", "공간", "expansion")):
        return sorted(records, key=lambda r:
                      _final_score(r, "expansion") if _final_score(r, "expansion") is not None else 99)
    if any(k in q for k in ("움직임", "쏟아", "튕", "movement")):
        return sorted(records, key=lambda r: -(_final_score(r, "movement") or 0))
    return sorted(records, key=lambda r: -(r.total_score if isinstance(r.total_score, (int, float)) else 0))


def _semantic_search(
    records: list[VideoRecord],
    query: str,
    top_k: int = 5,
) -> tuple[list[VideoRecord], dict[str, float]]:
    """실제 임베딩 검색. 실패 시 mock 정렬 fallback (sims dict 비어있음)."""
    if not query.strip():
        return _mock_search_sort(records, query), {}
    query_emb = _embed_query(query)
    if query_emb is None:
        return _mock_search_sort(records, query)[:top_k], {}

    all_results = repo.search_by_vector(query_emb, top_k=max(top_k, len(records)))
    filtered_slugs = {r.slug for r in records}
    out: list[VideoRecord] = []
    sims: dict[str, float] = {}
    for rec, sim in all_results:
        if rec.slug in filtered_slugs:
            out.append(rec)
            sims[rec.slug] = sim
        if len(out) >= top_k:
            break
    return out, sims


def _render_search_result_card(rec: VideoRecord, sim: Optional[float]) -> None:
    """컴팩트 검색 결과 카드 — 썸네일 X, 미니 바 + 점수 + 상세 보기 버튼."""
    final_scores = _final_scores_dict(rec)
    cat_badge = category_badge_html(rec.category)
    grade_badge = grade_badge_html(rec.grade)
    sim_html = (
        f'<span class="cl-badge" style="background:rgba(167,139,250,0.12);'
        f' color:#a78bfa; border-color:rgba(167,139,250,0.3);">'
        f'유사도 {sim:.3f}</span>' if sim is not None else ""
    )
    total_str = f"{rec.total_score:.2f}" if isinstance(rec.total_score, (int, float)) else "—"
    weakest_str = AXIS_KO.get(rec.weakest_axis or "", "—")
    publisher = rec.publisher or "—"

    st.markdown(
        f'<div class="cl-search-result-card">'
        f'<div class="cl-search-result-head">'
        f'<div style="display:flex; align-items:center; gap:8px;">'
        f'{cat_badge}'
        f'<span class="cl-search-result-title">{rec.game_name}</span>'
        f'</div>'
        f'<div style="display:flex; align-items:center; gap:6px;">'
        f'{sim_html}{grade_badge}'
        f'</div></div>'
        f'<div style="display:flex; align-items:center; gap:12px; margin-bottom:8px;">'
        f'<span style="font-size:11px; color:#71717a;">총점</span>'
        f'<span class="cl-num" style="font-size:13px; color:#fff;">{total_str}</span>'
        f'<span style="flex:1;"></span>'
        f'</div>'
        f'{mini_chart_html(final_scores)}'
        f'<div class="cl-search-result-meta">'
        f'<span>가장 약한 축: {weakest_str}</span>'
        f'<span>{rec.genre} · {publisher}</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    if st.button("상세 보기", key=f"search_open_{rec.slug}", use_container_width=True):
        st.session_state["nav_slug"] = rec.slug
        st.query_params["slug"] = rec.slug
        st.switch_page("pages/2_detail.py")


# ── 의미 검색 input + 칩 ──────────────────────────────────────────────────────
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
    st.session_state["search_query"] = ""
if "_search_input" not in st.session_state:
    st.session_state["_search_input"] = st.session_state["search_query"]


def _commit_search() -> None:
    st.session_state["search_query"] = st.session_state.get("_search_input", "")


def _set_search_query(q: str) -> None:
    st.session_state["search_query"] = q
    st.session_state["_search_input"] = q


example_queries = (
    "사운드가 약했던 경쟁사 영상",
    "움직임이 강한 자사 영상",
    "캐릭터 변화가 있는 영상",
)
search_cols = st.columns([5, 1])
with search_cols[0]:
    st.text_input(
        "search_query",
        placeholder="확장 축이 강한 시뮬레이션 게임 영상",
        label_visibility="collapsed",
        key="_search_input",
        on_change=_commit_search,
    )
with search_cols[1]:
    st.button(
        "찾기", type="primary", use_container_width=True,
        key="search_btn", on_click=_commit_search,
    )

chip_cols = st.columns([1, 2, 2, 2, 5])
chip_cols[0].markdown(
    '<div style="font-size:11px; color:#71717a; padding-top:6px;">예시:</div>',
    unsafe_allow_html=True,
)
for i, q in enumerate(example_queries):
    chip_cols[i + 1].button(
        q, key=f"chip_{i}", use_container_width=True,
        on_click=_set_search_query, args=(q,),
    )

active_query = (st.session_state.get("search_query") or "").strip()


# ── 검색 활성 시 — 결과 섹션 + st.stop() (이후 통계/6축/필터/그리드 차단) ──
def _clear_search() -> None:
    """검색어 + 입력 임시 키 둘 다 비움 → 전체 화면 (통계+6축+그리드) 복귀."""
    st.session_state["search_query"] = ""
    st.session_state["_search_input"] = ""


if active_query:
    sorted_results, _result_sims = _semantic_search(records, active_query, top_k=5)
    api_used = bool(_result_sims)
    badge_text = "임베딩 매칭" if api_used else "키워드 fallback (API 없음)"
    top_sim_val = max(_result_sims.values()) if _result_sims else None
    sim_part = f" · top sim {top_sim_val:.3f}" if top_sim_val is not None else ""

    # 검색 결과 헤더 + 상단 [전체 보기] 버튼
    head_cols = st.columns([5, 2])
    with head_cols[0]:
        st.markdown(
            f'<div style="font-size:13px; font-weight:500; color:#fff; margin: 16px 0 4px;">'
            f'검색 결과 <span style="color:#71717a; font-weight:400; font-size:11px;">'
            f'· “{active_query}” · {len(sorted_results)}편 ({badge_text}{sim_part})</span></div>',
            unsafe_allow_html=True,
        )
    with head_cols[1]:
        st.button(
            "← 전체 영상 보기",
            key="search_clear_btn_top",
            on_click=_clear_search,
            use_container_width=True,
            help="검색을 종료하고 통계+6축 그래프+전체 카드 그리드로 돌아갑니다",
        )

    if not sorted_results:
        st.markdown(
            '<div class="cl-empty-state" style="padding:32px 16px;">'
            '<h3>검색 결과가 없습니다</h3>'
            '<p>다른 표현으로 검색해보거나, 위의 <strong>← 전체 영상 보기</strong>를 눌러 전체 영상을 보세요.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        for rec in sorted_results:
            _render_search_result_card(rec, _result_sims.get(rec.slug))

        # 결과 카드 아래에도 동일 [전체 보기] 버튼 — 긴 결과 스크롤 후 쉽게 복귀
        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
        bottom_cols = st.columns([2, 3, 2])
        with bottom_cols[1]:
            st.button(
                "← 전체 영상 보기",
                key="search_clear_btn_bottom",
                on_click=_clear_search,
                use_container_width=True,
                help="검색을 종료하고 통계+6축 그래프+전체 카드 그리드로 돌아갑니다",
            )

    st.stop()


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


# ─── 필터 적용 + 정렬 (active_query 비활성 분기 — 위에서 st.stop() 통과) ──
def _apply_filters(records: list[VideoRecord]) -> list[VideoRecord]:
    out = records
    if sel_categories:
        out = [r for r in out if r.category in sel_categories]
    if sel_grades:
        out = [r for r in out if r.grade in sel_grades]
    if sel_genres:
        out = [r for r in out if r.genre in sel_genres]
    return out


sorted_records = sorted(
    _apply_filters(records),
    key=lambda r: -(r.total_score if isinstance(r.total_score, (int, float)) else 0),
)

st.markdown(
    f'<div style="font-size:11px; color:#71717a; margin: 8px 0 12px;">'
    f'정렬: 총점 내림차순 · 표시 {len(sorted_records)}편</div>',
    unsafe_allow_html=True,
)


# ─── 카드 그리드 (2 컬럼) ────────────────────────────────────────────────────
def _render_card(rec: VideoRecord, *, is_deleted: bool = False,
                 sim: Optional[float] = None) -> None:
    final_scores = _final_scores_dict(rec)
    grade = grade_badge_html(rec.grade)
    cat_badge = category_badge_html(rec.category)
    sim_badge = (
        f'<span class="cl-badge" style="background:rgba(167,139,250,0.12);'
        f' color:#a78bfa; border-color:rgba(167,139,250,0.3);">'
        f'유사도 {sim:.3f}</span>'
        if sim is not None else ""
    )

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

    deleted_badge = ""
    extra_card_class = ""
    if is_deleted:
        extra_card_class = " cl-archive-card-deleted"
        ts = (rec.deleted_at or "").replace("T", " ")[:16] if rec.deleted_at else ""
        deleted_badge = (
            '<span class="cl-badge" style="background:rgba(113,113,122,0.18); '
            f'color:#a1a1aa;">삭제됨 · {ts}</span>'
        )

    head_right = deleted_badge if is_deleted else grade
    mini_tip = tip_html(
        "6축 미니 차트",
        "왼쪽부터 움직임·성장·확장(라벤더, 변화 3축), 카메라·컬러·사운드(민트, 연출 3축) 순이에요. 막대 길이가 점수예요.",
    )
    st.markdown(
        f'<div class="cl-archive-card{extra_card_class}">'
        f'<div class="cl-archive-card-head">'
        f'<div style="display:flex; align-items:center; gap:8px;">'
        f'{cat_badge}'
        f'<span style="font-size:13px; font-weight:500; color:#fff;">{rec.game_name}</span>'
        f'</div>'
        f'<div style="display:flex; align-items:center; gap:6px;">'
        f'{sim_badge}{head_right}'
        f'</div></div>'
        f'{thumb_html}'
        f'<div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">'
        f'<span style="font-size:11px; color:#71717a;">총점</span>'
        f'<span class="cl-num" style="font-size:14px;">{total_str}</span>'
        f'</div>'
        f'<div style="display:flex; align-items:center; margin: 0 0 6px;">'
        f'<span style="font-size:10px; color:#71717a;">변화 3축 · 연출 3축 점수</span>'
        f'{mini_tip}'
        f'</div>'
        f'{mini_chart_html(final_scores)}'
        f'<div style="display:flex; align-items:center; justify-content:space-between; margin-top:10px;">'
        f'<span style="font-size:10px; color:#71717a;">가장 약한 축: {weakest_str}</span>'
        f'<span style="font-size:10px; color:#71717a;">{rec.genre} · {publisher}</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    if is_deleted:
        # 삭제된 카드 — "복원" 버튼만 (자세히 보기 / 영구 삭제 두 갈래)
        btn_cols = st.columns([4, 3])
        with btn_cols[0]:
            if st.button("↩ 복원", key=f"restore_{rec.slug}", type="primary",
                         use_container_width=True, help="휴지통 복귀 — 자산 + 카드 다시 활성화"):
                if isinstance(repo, JsonRepository):
                    if repo.restore_video(rec.slug):
                        st.toast(f"{rec.game_name} 복원 완료", icon="↩️")
                        time.sleep(0.5)
                        st.rerun()
        with btn_cols[1]:
            if st.button("🗑 영구 삭제", key=f"hard_delete_{rec.slug}",
                         use_container_width=True,
                         help="휴지통과 cache JSON 모두 정리 (복원 불가)"):
                st.session_state["pending_delete"] = rec.slug
                st.session_state["pending_delete_hard_default"] = True
    else:
        btn_cols = st.columns([6, 1])
        with btn_cols[0]:
            if st.button("자세히 보기", key=f"open_{rec.slug}", use_container_width=True):
                st.session_state["nav_slug"] = rec.slug
                st.query_params["slug"] = rec.slug
                st.switch_page("pages/2_detail.py")
        with btn_cols[1]:
            if st.button("🗑", key=f"delete_{rec.slug}", use_container_width=True,
                          help="이 영상을 휴지통으로 이동 (soft delete)"):
                st.session_state["pending_delete"] = rec.slug
                st.session_state["pending_delete_hard_default"] = False


@st.dialog("영상 삭제 확인")
def _confirm_delete_dialog(slug: str):
    """삭제 확인 모달 — soft 기본, 영구 삭제 체크박스로 hard 전환."""
    target = repo.get_video(slug)
    if target is None:
        st.error(f"slug '{slug}' 를 찾을 수 없습니다.")
        return
    is_seed = slug in {"burger_please_drive_thru", "pizza_ready_break", "snake_clash_morph",
                       "twerk_race_gate", "kingshot_expansion"}
    cat_ko = CATEGORY_KO.get(target.category, target.category)

    st.markdown(
        f"<div style='font-size:14px; color:#fff; font-weight:500; margin-bottom:8px;'>"
        f"{target.game_name} <span style='color:#a1a1aa; font-weight:400;'>({cat_ko})</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-size:12px; color:#a1a1aa; margin-bottom:12px;'>"
        "기본은 <strong style='color:#fff;'>휴지통 이동(복원 가능)</strong>입니다. "
        "자산은 <code>data/.trash/{slug}/</code> 로 이동하고 카드는 '삭제됨' 상태로 표시됩니다.</div>",
        unsafe_allow_html=True,
    )

    hard_default = bool(st.session_state.get("pending_delete_hard_default", False))
    hard_delete = st.checkbox(
        "영구 삭제 (복원 불가)",
        value=hard_default,
        key=f"hard_delete_check_{slug}",
        help="체크 시 cache JSON · 임베딩 · mp4 · frames · script 모두 즉시 정리됩니다.",
    )

    if hard_delete:
        st.markdown(
            "<div style='font-size:11px; color:#ef4444; background:rgba(239,68,68,0.06);"
            " border:0.5px solid rgba(239,68,68,0.2); border-radius:6px;"
            " padding:8px 12px; margin: 8px 0 12px;'>"
            "⚠ 영구 삭제 모드 — 휴지통과 모든 자산이 즉시 제거되며 되돌릴 수 없습니다.</div>",
            unsafe_allow_html=True,
        )
        if is_seed:
            st.markdown(
                "<div style='font-size:11px; color:#f5a524; background:rgba(245,165,36,0.06);"
                " border:0.5px solid rgba(245,165,36,0.2); border-radius:6px;"
                " padding:8px 12px; margin: 0 0 12px;'>"
                "⚠ 시드 영구 삭제 — 페이지 진입 시 자동 복원되지 않습니다 "
                "(<strong>시드 복원</strong> 버튼으로만 복원).</div>",
                unsafe_allow_html=True,
            )

    cancel_col, delete_col = st.columns(2)
    if cancel_col.button("취소", key=f"cancel_delete_{slug}", use_container_width=True):
        st.session_state.pop("pending_delete", None)
        st.session_state.pop("pending_delete_hard_default", None)
        st.rerun()
    delete_label = "영구 삭제" if hard_delete else "휴지통으로 이동"
    if delete_col.button(delete_label, key=f"confirm_delete_{slug}", type="primary",
                          use_container_width=True):
        ok = repo.delete_video(slug, hard=hard_delete)
        st.session_state.pop("pending_delete", None)
        st.session_state.pop("pending_delete_hard_default", None)
        if ok:
            st.toast(f"{target.game_name} 삭제 완료", icon="🗑️")
        else:
            st.toast(f"{target.game_name} 자산 일부 누락 (이미 삭제됨)", icon="⚠️")
        time.sleep(0.5)
        st.rerun()


# ─── 삭제 다이얼로그 트리거 ──────────────────────────────────────────────────
_pending = st.session_state.get("pending_delete")
if _pending:
    _confirm_delete_dialog(_pending)


grid_cols = st.columns(2)
for idx, rec in enumerate(sorted_records):
    with grid_cols[idx % 2]:
        _render_card(rec)


# ─── 삭제된 영상 섹션 (토글 켜졌을 때만) ─────────────────────────────────────
if show_deleted and deleted_records:
    st.markdown(
        f'<div style="margin: 32px 0 12px;">'
        f'<h2 style="margin:0;">삭제된 영상 <span class="cl-num" style="color:#71717a; '
        f'font-size:14px; font-weight:400;">({len(deleted_records)}편 · 휴지통)</span></h2>'
        f'<p style="font-size:11px; color:#71717a; margin:4px 0 0;">'
        f'카드의 <strong style="color:#a1a1aa;">↩ 복원</strong> 으로 다시 활성화, '
        f'<strong style="color:#a1a1aa;">🗑 영구 삭제</strong> 로 휴지통까지 정리.</p>'
        f'</div>',
        unsafe_allow_html=True,
    )
    deleted_cols = st.columns(2)
    for idx, rec in enumerate(sorted(deleted_records, key=lambda r: r.deleted_at or "", reverse=True)):
        with deleted_cols[idx % 2]:
            _render_card(rec, is_deleted=True)
