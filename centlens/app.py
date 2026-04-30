"""CentLens Streamlit 진입점.

진입 시 페이지 1(새 영상 분석)으로 자동 라우팅한다 — 첫 화면을 분석 입력 폼으로 두어
"광고 집행 전 사전 점검 도구" 정체성이 즉시 드러나도록 한다.

LangSmith trace 활성화를 위해 LangGraph import보다 먼저 ``load_dotenv()`` 호출.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(_PROJECT_ROOT / ".env")

import streamlit as st  # noqa: E402

from centlens.ui.styles import configure_page  # noqa: E402

configure_page(page_title="CentLens")

# 진입 시 페이지 1로 보낸다.
st.switch_page("pages/1_analyze.py")
