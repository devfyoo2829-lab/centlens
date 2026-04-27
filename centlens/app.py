"""CentLens Streamlit 진입점.

진입 시 페이지 3(분석한 영상 모음)으로 자동 라우팅한다 — 시연 첫 화면이 카드 그리드여야
"5편 자산을 한눈에 보고 의미 검색으로 들어가는" 플로우가 자연스럽다.

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

# 진입 시 페이지 3으로 보낸다.
st.switch_page("pages/3_분석한_영상_모음.py")
