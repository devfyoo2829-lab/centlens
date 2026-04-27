"""CentLens 공통 디자인 토큰 · CSS · UI 헬퍼.

3개 페이지(`pages/1_새_영상_분석.py`, `pages/2_영상_상세.py`, `pages/3_분석한_영상_모음.py`)와
메인 진입점 `app.py`가 공유하는 시각 토큰과 컴포넌트 헬퍼를 한 곳에 모은다.

설계 원칙:
- 폰트/CSS는 페이지마다 한 번 ``inject_base_styles()`` 호출로 주입.
- 6축 게이지·미니 차트·등급 뱃지·관점차이 카드는 plotly 대신 HTML로 그린다 — 시안 정확도 + 번들 크기 모두 우월.
- 툴팁(``cl-tip``)은 시안 README의 30개 명세를 그대로 따름. ``tip_html()``로 inline 삽입.
"""

from typing import Optional

import streamlit as st


# ─── 디자인 토큰 ──────────────────────────────────────────────────────────────
COLOR_BG_PAGE = "#18181b"
COLOR_BG_APP = "#000000"
COLOR_BG_CARD = "#0a0a0a"
COLOR_BG_HOVER = "#1a1a1a"
COLOR_BORDER = "#262626"
COLOR_BORDER_STRONG = "#404040"

COLOR_TEXT_PRIMARY = "#ffffff"
COLOR_TEXT_SECONDARY = "#a1a1aa"
COLOR_TEXT_MUTED = "#71717a"
COLOR_TEXT_HINT = "#d4d4d8"

COLOR_LINK = "#0070f3"

GRADE_COLORS: dict[str, str] = {
    "strong": "#00d68f",
    "medium": "#f5a524",
    "weak": "#71717a",
}

GRADE_KO: dict[str, str] = {
    "strong": "우수",
    "medium": "보통",
    "weak": "약함",
}

CATEGORY_KO: dict[str, str] = {
    "new": "자사 신규",
    "competitor": "경쟁사",
    "trend": "시장 트렌드",
}

AXES: tuple[str, ...] = ("movement", "growth", "expansion", "camera", "color", "sound")
AXIS_KO: dict[str, str] = {
    "movement": "움직임",
    "growth": "성장",
    "expansion": "확장",
    "camera": "카메라",
    "color": "컬러",
    "sound": "사운드",
}
AXIS_GROUP: dict[str, str] = {
    "movement": "change",
    "growth": "change",
    "expansion": "change",
    "camera": "production",
    "color": "production",
    "sound": "production",
}
AXIS_GROUP_COLOR: dict[str, str] = {
    "change": "#a78bfa",       # 라벤더
    "production": "#34d399",    # 민트
}


# ─── 페이지 식별자 → 파일 경로 매핑 ──────────────────────────────────────────
# 헤더 탭 라우팅에 쓰인다. 한국어 파일명을 그대로 사용한다.
PAGE_PATHS: dict[str, str] = {
    "upload":  "pages/1_새_영상_분석.py",
    "detail":  "pages/2_영상_상세.py",
    "archive": "pages/3_분석한_영상_모음.py",
}
PAGE_LABELS: dict[str, str] = {
    "upload":  "새 영상 분석",
    "detail":  "영상 상세",
    "archive": "분석한 영상 모음",
}


# ─── 베이스 스타일 (페이지마다 1회 주입) ─────────────────────────────────────
_BASE_CSS = """<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── 전역 다크 톤 ────────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], .main, .block-container {
  background: #18181b !important;
  color: #ffffff;
  font-family: 'Pretendard', 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.6;
}
.block-container {
  max-width: 1100px !important;
  padding: 24px 24px 48px 24px !important;
}
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stSidebar"], [data-testid="stSidebarNav"], [data-testid="stSidebarNavItems"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
footer, [data-testid="stStatusWidget"] { display: none !important; }

h1 { font-size: 22px !important; font-weight: 500 !important; margin: 0 0 8px 0 !important; }
h2 { font-size: 16px !important; font-weight: 500 !important; margin: 0 0 12px 0 !important; }
h3 { font-size: 14px !important; font-weight: 500 !important; }
p, span, div, label { color: inherit; }

a { color: #0070f3; text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── 헤더 / 탭 네비 ──────────────────────────────────────────────────────── */
.cl-header {
  display: flex; align-items: center; justify-content: space-between;
  padding-bottom: 20px; border-bottom: 0.5px solid #262626; margin-bottom: 28px;
}
.cl-header-left { display: flex; align-items: center; gap: 12px; }
.cl-logo-square {
  width: 28px; height: 28px; background: #fff; color: #000; border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  font-weight: 500; font-size: 14px;
}
.cl-logo-name { font-weight: 500; font-size: 15px; color: #fff; }
.cl-logo-tagline { font-size: 13px; color: #71717a; margin-left: 8px; }
.cl-tabs { display: flex; gap: 4px; }
.cl-tab {
  background: transparent; color: #a1a1aa; border: 0.5px solid transparent;
  padding: 6px 12px; border-radius: 6px; font-size: 13px; cursor: pointer;
  text-decoration: none; display: inline-block;
}
.cl-tab:hover { color: #fff; text-decoration: none; }
.cl-tab-active { background: #0a0a0a; color: #fff; border: 0.5px solid #262626; }

/* ── 카드/뱃지/입력 컴포넌트 ─────────────────────────────────────────────── */
.cl-card {
  background: #0a0a0a; border: 0.5px solid #262626; border-radius: 12px;
  padding: 20px; margin-bottom: 16px;
}
.cl-card-head { font-size: 13px; color: #a1a1aa; margin-bottom: 12px; font-weight: 500; }
.cl-card-sub { font-size: 11px; color: #71717a; margin-top: 2px; }

.cl-section-title { font-size: 16px; font-weight: 500; margin: 0; }
.cl-label-upper {
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 500;
}

.cl-badge {
  background: #1a1a1a; color: #a1a1aa; padding: 2px 7px; border-radius: 4px;
  font-size: 11px; border: 0.5px solid #262626;
}
.cl-badge-grade {
  padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 500;
  background: #1a1a1a; border: 0.5px solid;
  font-family: 'Pretendard', 'Inter', sans-serif;
}
.cl-mono { font-family: 'JetBrains Mono', 'Inter', monospace; }
.cl-num { font-family: 'JetBrains Mono', monospace; font-weight: 500; }

/* ── Streamlit 위젯 다크 톤 보정 ─────────────────────────────────────────── */
.stTextInput input, .stTextArea textarea {
  background: #000 !important;
  color: #fff !important;
  border: 0.5px solid #262626 !important;
  border-radius: 6px !important;
  font-size: 13px !important;
  font-family: 'Pretendard', 'Inter', sans-serif !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder { color: #71717a !important; }
.stFileUploader { border: 1px dashed #404040 !important; border-radius: 8px !important; background: #0a0a0a !important; }
.stFileUploader > section { background: transparent !important; padding: 16px !important; }
.stFileUploader label { color: #a1a1aa !important; }

/* segmented_control */
[data-testid="stSegmentedControl"] button {
  background: transparent !important; color: #a1a1aa !important;
  border: 0.5px solid #262626 !important; font-size: 12px !important;
}
[data-testid="stSegmentedControl"] button[aria-pressed="true"] {
  background: #ffffff !important; color: #000000 !important; border-color: #fff !important;
}

/* button */
.stButton > button {
  background: #ffffff; color: #000; border: none; padding: 10px 16px;
  border-radius: 8px; font-size: 13px; font-weight: 500;
  font-family: 'Pretendard', 'Inter', sans-serif;
}
.stButton > button:hover { background: #e4e4e7; color: #000; }
.stButton > button[kind="secondary"] {
  background: #1a1a1a; color: #fff; border: 0.5px solid #262626;
}
.stButton > button[kind="secondary"]:hover { background: #262626; border-color: #404040; }

/* ── 6축 게이지 막대 ─────────────────────────────────────────────────────── */
.cl-axis-row { margin-bottom: 14px; }
.cl-axis-head {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;
}
.cl-axis-name { font-size: 13px; color: #fff; }
.cl-axis-name-muted { font-size: 13px; color: #71717a; }
.cl-axis-meta { display: flex; align-items: center; gap: 12px; }
.cl-axis-ab {
  font-size: 11px; color: #71717a;
  font-family: 'JetBrains Mono', monospace;
}
.cl-axis-final {
  font-size: 14px; font-weight: 500; min-width: 36px; text-align: right;
  font-family: 'JetBrains Mono', monospace;
}
.cl-axis-bar {
  height: 4px; background: #1a1a1a; border-radius: 2px; overflow: hidden;
}
.cl-axis-bar-fill { height: 100%; }

.cl-divergence-flag {
  background: rgba(245, 165, 36, 0.1); color: #f5a524;
  padding: 1px 6px; border-radius: 3px; font-size: 10px;
  border: 0.5px solid rgba(245, 165, 36, 0.3); margin-left: 8px;
}

/* ── 6축 미니 차트 (카드 안) ─────────────────────────────────────────────── */
.cl-mini { display: grid; grid-template-columns: repeat(6, 1fr); gap: 3px; }
.cl-mini-cell {
  height: 18px; background: #1a1a1a; border-radius: 2px; position: relative;
}
.cl-mini-fill {
  position: absolute; bottom: 0; left: 0; right: 0; border-radius: 2px;
}

/* ── 관점 차이 카드 (앰버 톤) ────────────────────────────────────────────── */
.cl-divergence-card {
  background: rgba(245, 165, 36, 0.04);
  border: 0.5px solid rgba(245, 165, 36, 0.2);
  border-radius: 12px; padding: 20px; margin-bottom: 24px;
}
.cl-divergence-head {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;
}
.cl-divergence-title { font-size: 13px; font-weight: 500; color: #fff; }
.cl-divergence-diff {
  background: rgba(245, 165, 36, 0.1); color: #f5a524;
  padding: 4px 10px; border-radius: 6px; font-size: 11px;
  border: 0.5px solid rgba(245, 165, 36, 0.3);
  font-family: 'JetBrains Mono', monospace; font-weight: 500;
}
.cl-divergence-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.cl-divergence-pane {
  background: #0a0a0a; border: 0.5px solid #262626; border-radius: 8px; padding: 14px;
}
.cl-divergence-pane-head {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;
}
.cl-divergence-pane-rationale {
  font-size: 12px; color: #d4d4d8; margin: 0; line-height: 1.6;
}

/* ── 타임라인 / 통계 셀 ──────────────────────────────────────────────────── */
.cl-timing-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; margin-top: 14px; }
.cl-timing-cell {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 10px; background: #000; border-radius: 4px;
}
.cl-timing-cell-emph { border: 0.5px solid #404040; }
.cl-timing-label { font-size: 11px; color: #a1a1aa; }
.cl-timing-value { font-size: 11px; color: #71717a; font-family: 'JetBrains Mono', monospace; }
.cl-timing-emph .cl-timing-label, .cl-timing-emph .cl-timing-value { color: #fff; }

.cl-stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
.cl-stat {
  background: #0a0a0a; border: 0.5px solid #262626; border-radius: 12px; padding: 16px;
}
.cl-stat-label { font-size: 11px; color: #71717a; display: flex; align-items: center; }
.cl-stat-value {
  font-size: 24px; font-weight: 500; font-family: 'JetBrains Mono', monospace; margin-top: 4px;
}
.cl-stat-sub { font-size: 10px; color: #71717a; margin-top: 2px; }

/* ── 카드 그리드 (페이지 3) ─────────────────────────────────────────────── */
.cl-archive-card {
  background: #0a0a0a; border: 0.5px solid #262626; border-radius: 12px;
  padding: 16px; transition: border-color 0.15s;
}
.cl-archive-card:hover { border-color: #404040; }
.cl-archive-card-head {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;
}
.cl-archive-thumb {
  position: relative;
  height: 280px;
  background: #000;
  border-radius: 6px;
  border: 0.5px solid #262626;
  margin-bottom: 12px;
  overflow: hidden;
  cursor: pointer;
}
.cl-archive-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.25s ease;
}
.cl-archive-thumb:hover .cl-archive-thumb-img {
  transform: scale(1.02);
}
.cl-archive-thumb::before {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.2);
  transition: opacity 0.25s ease;
  z-index: 1;
  pointer-events: none;
}
.cl-archive-thumb:hover::before {
  opacity: 0;
}
.cl-archive-thumb::after {
  content: '';
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(calc(-50% + 2px), -50%);
  width: 0;
  height: 0;
  border-left: 14px solid rgba(255, 255, 255, 0.92);
  border-top: 9px solid transparent;
  border-bottom: 9px solid transparent;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.7));
  z-index: 2;
  pointer-events: none;
  transition: transform 0.25s ease, opacity 0.25s ease;
}
.cl-archive-thumb:hover::after {
  transform: translate(calc(-50% + 2px), -50%) scale(1.1);
}
.cl-archive-thumb-empty {
  display: flex; align-items: center; justify-content: center;
  width: 100%; height: 100%;
  color: #71717a; font-size: 11px;
}

/* ── 영상 / 프레임 fallback placeholder ─────────────────────────────────── */
.cl-fallback {
  background: #0a0a0a; border: 0.5px dashed #404040; border-radius: 8px;
  padding: 24px; text-align: center; color: #a1a1aa; font-size: 12px; line-height: 1.6;
}
.cl-frame-placeholder {
  aspect-ratio: 16 / 9; background: #1a1a1a; border-radius: 4px;
  border: 0.5px solid #262626; display: flex; align-items: center; justify-content: center;
  color: #71717a; font-size: 10px;
}

/* ── 툴팁 (cl-tip) ───────────────────────────────────────────────────────── */
.cl-tip {
  position: relative; display: inline-flex; align-items: center; cursor: help; margin-left: 4px;
}
.cl-tip-icon {
  width: 14px; height: 14px; border-radius: 50%; border: 0.5px solid #404040;
  display: inline-flex; align-items: center; justify-content: center;
  color: #71717a; font-size: 9px; font-weight: 500; font-style: italic;
  font-family: Georgia, serif;
}
.cl-tip:hover .cl-tip-icon { color: #fff; border-color: #71717a; }
.cl-tip-content {
  visibility: hidden; opacity: 0; position: absolute; bottom: calc(100% + 8px);
  left: 50%; transform: translateX(-50%);
  background: #0a0a0a; border: 0.5px solid #404040; border-radius: 8px;
  padding: 10px 12px; width: 240px; font-size: 11px; line-height: 1.5;
  color: #d4d4d8; z-index: 100; text-align: left; font-weight: 400; font-style: normal;
  transition: opacity 0.15s, visibility 0.15s; pointer-events: none;
}
.cl-tip:hover .cl-tip-content { visibility: visible; opacity: 1; }
.cl-tip-content::after {
  content: ''; position: absolute; top: 100%; left: 50%;
  transform: translateX(-50%); border: 4px solid transparent; border-top-color: #404040;
}
.cl-tip-content strong { color: #fff; font-weight: 500; }

/* ── 마케터 코멘트 영역 ─────────────────────────────────────────────────── */
.cl-comment-head { font-size: 13px; font-weight: 500; }
.cl-comment-hint { font-size: 11px; color: #71717a; margin: 0 0 12px; }

</style>
"""


def configure_page(page_title: str = "CentLens") -> None:
    """모든 페이지에서 가장 먼저 호출되는 page config + 베이스 스타일 주입."""
    st.set_page_config(
        page_title=page_title,
        page_icon="◎",
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={"About": None, "Get help": None, "Report a bug": None},
    )
    st.markdown(_BASE_CSS, unsafe_allow_html=True)


def render_header(active: str) -> None:
    """상단 로고 + 탭 네비. ``active``: 'upload' | 'detail' | 'archive'."""
    tabs_html_parts: list[str] = []
    for key, label in PAGE_LABELS.items():
        cls = "cl-tab cl-tab-active" if key == active else "cl-tab"
        # 페이지 라우팅은 anchor href — multipage app에서 한국어 파일명 그대로 동작.
        href = "/" + PAGE_PATHS[key].split("/")[-1].replace(".py", "")
        tabs_html_parts.append(
            f'<a class="{cls}" href="{href}" target="_self">{label}</a>'
        )
    tabs_html = "".join(tabs_html_parts)

    show_tagline = active == "upload"
    tagline_html = (
        '<span class="cl-logo-tagline">슈퍼센트 6축 프레임으로 광고 영상을 들여다보는 도구</span>'
        if show_tagline else ""
    )
    st.markdown(
        f"""
        <div class="cl-header">
          <div class="cl-header-left">
            <div class="cl-logo-square">CL</div>
            <span class="cl-logo-name">CentLens</span>
            {tagline_html}
          </div>
          <div class="cl-tabs">{tabs_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── 인라인 HTML 헬퍼 ─────────────────────────────────────────────────────────
def tip_html(title: str, body: str) -> str:
    """⚠ 호출자가 직접 ``unsafe_allow_html=True`` 컨텍스트에서 사용해야 한다.

    title/body의 HTML 특수문자는 호출 측에서 이미 안전한 한국어 문자열을 넣는다고 가정한다.
    """
    return (
        '<span class="cl-tip">'
        '<span class="cl-tip-icon">i</span>'
        f'<span class="cl-tip-content"><strong>{title}</strong><br>{body}</span>'
        "</span>"
    )


def grade_badge_html(grade: Optional[str]) -> str:
    """등급 뱃지 HTML. None이면 '—'."""
    if not grade:
        return '<span class="cl-badge">—</span>'
    color = GRADE_COLORS.get(grade, COLOR_TEXT_MUTED)
    label = GRADE_KO.get(grade, grade)
    return (
        f'<span class="cl-badge-grade" style="color:{color}; border-color:{color};">'
        f"{label}</span>"
    )


def category_badge_html(category: Optional[str]) -> str:
    label = CATEGORY_KO.get(category or "", category or "—")
    return f'<span class="cl-badge">{label}</span>'


def axis_gauge_html(
    axis: str,
    a_score: Optional[float],
    b_score: Optional[float],
    final_score: Optional[float],
    *,
    is_weakest: bool = False,
    diverged: bool = False,
    tip_title: Optional[str] = None,
    tip_body: Optional[str] = None,
) -> str:
    """6축 게이지 한 줄 (이름 · 1차/검증 · final · 막대)."""
    name_class = "cl-axis-name-muted" if is_weakest else "cl-axis-name"
    name_text = f"{AXIS_KO[axis]} (가장 약한 축)" if is_weakest else AXIS_KO[axis]
    name_with_tip = name_text + (
        tip_html(tip_title, tip_body) if (tip_title and tip_body) else ""
    )
    diverge_flag = (
        '<span class="cl-divergence-flag">관점 차이 큼</span>' if diverged else ""
    )

    a_str = f"{a_score:.2f}" if a_score is not None else "—"
    b_str = f"{b_score:.2f}" if b_score is not None else "—"
    final_str = f"{final_score:.2f}" if final_score is not None else "—"

    pct = max(0.0, min(100.0, (final_score / 5.0) * 100.0)) if final_score is not None else 0.0
    color = AXIS_GROUP_COLOR[AXIS_GROUP[axis]]

    return (
        '<div class="cl-axis-row">'
        '<div class="cl-axis-head">'
        f'<div style="display:flex;align-items:center;"><span class="{name_class}">{name_with_tip}</span>{diverge_flag}</div>'
        '<div class="cl-axis-meta">'
        f'<span class="cl-axis-ab">1차 {a_str} · 검증 {b_str}</span>'
        f'<span class="cl-axis-final">{final_str}</span>'
        "</div></div>"
        f'<div class="cl-axis-bar"><div class="cl-axis-bar-fill" style="width:{pct:.1f}%; background:{color};"></div></div>'
        "</div>"
    )


def mini_chart_html(final_scores: dict[str, Optional[float]]) -> str:
    """카드 안 6축 미니 막대. 변화 3축(라벤더) + 연출 3축(민트)."""
    cells: list[str] = []
    for ax in AXES:
        s = final_scores.get(ax)
        h_pct = max(0.0, min(100.0, (s / 5.0) * 100.0)) if s is not None else 0.0
        color = AXIS_GROUP_COLOR[AXIS_GROUP[ax]]
        cells.append(
            '<div class="cl-mini-cell">'
            f'<div class="cl-mini-fill" style="height:{h_pct:.1f}%; background:{color};"></div>'
            "</div>"
        )
    return f'<div class="cl-mini">{"".join(cells)}</div>'


def fallback_box_html(
    message: str = "영상 파일이 로드되지 않았습니다. (배포 환경에서는 별도 처리 필요)",
    height_px: int = 112,
) -> str:
    return (
        f'<div class="cl-fallback" style="min-height:{height_px}px;'
        ' display:flex; align-items:center; justify-content:center;">'
        f"{message}</div>"
    )
