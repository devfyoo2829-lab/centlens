# 06. 바이브 코딩 지시 프롬프트

본 문서는 Claude Code 또는 다른 코드 생성 LLM에 전달할 구현 명세 전문이다.

---

## 프롬프트 본문

````
당신은 시니어 풀스택 엔지니어입니다.
아래 명세에 따라 "CentLens"를 LangGraph 기반 멀티에이전트 시스템으로 구현해주세요.

# 제품 개요

슈퍼센트 광고 컨텐츠 마케터·크리에이티브 디렉터의 직무에 명시된
"광고 소재의 과거 성과 분석", "신규 광고 소재 발굴",
"경쟁사 광고 소재 벤치마킹", "시장 트렌드 분석" 업무를,
슈퍼센트가 자체 정의한 변화 3축 + 연출 3축 프레임으로
자동 분해해주는 분석 어시스턴트.

핵심 원칙: AI는 점수를 매기되, 결정은 마케터가 합니다.
("data-driven insights + human oversight" — 슈퍼센트 UA 운영 철학,
Pizza Ready UA 전략 글에서 인용)

# 아키텍처: LangGraph StateGraph 기반 멀티에이전트

각 평가 축을 독립된 Judge 노드로 분리하여
축 간 일관성 편향(consistency bias)을 원천 차단합니다.
6개 Judge 노드는 병렬 실행되어 처리 시간을 단축합니다.

## 노드 구성 (총 10개)

| 노드 | 역할 | LLM 호출 |
|---|---|---|
| ① Preprocessor | ffmpeg 프레임 추출 + Whisper STT | ❌ |
| ② Movement Judge | 움직임 축 평가 (변화) | ✅ |
| ③ Growth Judge | 성장 축 평가 (변화) | ✅ |
| ④ Expansion Judge | 확장 축 평가 (변화) | ✅ |
| ⑤ Camera Judge | 카메라 축 평가 (연출) | ✅ |
| ⑥ Color Judge | 컬러 축 평가 (연출) | ✅ |
| ⑦ Sound Judge | 사운드 축 평가 (연출) | ✅ |
| ⑧ Cross-Check | A/B 양방향 교차 채점 | ✅ |
| ⑨ Grade Calculator | weakest-link 등급 산출 | ❌ |
| ⑩ Embedder | 시맨틱 검색용 임베딩 생성 | ❌ |

## 흐름

START
  → ① Preprocessor
  → [② Movement, ③ Growth, ④ Expansion, ⑤ Camera, ⑥ Color, ⑦ Sound] (병렬)
  → ⑧ Cross-Check (6축 결과 통합 + 재검증)
  → ⑨ Grade Calculator
  → ⑩ Embedder
  → END (Supabase 저장)

# 평가 루브릭 (슈퍼센트 자체 정의 — 절대 변경 금지)

출처: Annie, "⚡️실패없는 크리에이티브 기획 바이블",
슈퍼센트 블로그, 2025.06.10

## 변화 3축
1. **움직임 (Movement)**: "튕기고, 무너지고, 쏟아지는 장면"
2. **성장 (Growth)**: "플레이어가 변화하는 장면"
3. **확장 (Expansion)**: "넓어지는 공간, 변화하는 시스템"

## 연출 3축
4. **카메라 (Camera)**: "시점을 바꿔 공간을 보여주거나, 슬로우/가속으로
   흐름을 조절하거나, 이동하는 카메라로 외부 상황과 정보를 자연스럽게 드러냄"
5. **컬러 (Color)**: "메인 오브젝트에는 선명한 색을, 배경엔 차분한 톤을 써
   집중을 유도하고, 위험·금지 상황엔 붉은 계열을 사용해 직관적으로 인식"
6. **사운드 (Sound)**: "변화 순간에 효과음을 맞춰 몰입을 강화하고,
   반복 조작에는 짧은 사운드로 리듬을 더하고, 장면 전환에는 공간감 있는 음향"

각 축은 5점 척도 + 평가 근거 한국어 1~2문장.

# 기술 스택
- Python 3.11
- Streamlit (멀티페이지 UI)
- LangGraph (멀티에이전트 오케스트레이션)
- Anthropic Claude Sonnet 4.5 (claude-sonnet-4-5)
- OpenAI Whisper API (영상 STT)
- OpenAI text-embedding-3-small (시맨틱 검색)
- Supabase (PostgreSQL + pgvector)
- ffmpeg-python

# 디렉토리 구조

centlens/
├── app.py
├── pages/
│   ├── 1_업로드_및_분석.py
│   ├── 2_영상_상세.py
│   └── 3_누적_데이터.py
├── graph/
│   ├── state.py                # CentLensState TypedDict 정의
│   ├── builder.py               # StateGraph 빌더
│   └── nodes/
│       ├── preprocessor.py      # ① 프레임 + STT
│       ├── movement_judge.py    # ② 움직임 축
│       ├── growth_judge.py      # ③ 성장 축
│       ├── expansion_judge.py   # ④ 확장 축
│       ├── camera_judge.py      # ⑤ 카메라 축
│       ├── color_judge.py       # ⑥ 컬러 축
│       ├── sound_judge.py       # ⑦ 사운드 축
│       ├── cross_check.py       # ⑧ A/B 교차 채점
│       ├── grade_calculator.py  # ⑨ weakest-link
│       └── embedder.py          # ⑩ 임베딩
├── core/
│   ├── prompts.py               # 모든 LLM 프롬프트 중앙화
│   ├── repository.py            # Supabase CRUD
│   └── demo_loader.py           # 사전 처리 캐시 로드
├── schema.sql
├── demo_cache/                  # 사전 처리된 데모 결과 5편
└── requirements.txt

# State 정의 (graph/state.py)

```python
from typing import TypedDict, Optional, Literal

class AxisScore(TypedDict):
    score: float          # 1.0 ~ 5.0
    rationale: str        # 한국어 1~2문장 평가 근거
    confidence: float     # 0.0 ~ 1.0

class CentLensState(TypedDict):
    # 입력
    video_path: str
    category: Literal['new', 'competitor', 'trend']
    game_name: str
    genre: str

    # ① Preprocessor 출력
    frames: list[str]              # 프레임 이미지 경로 5개
    script: str                    # Whisper STT 결과

    # ②~⑦ Judge 노드 출력 (1차 채점)
    movement_a: Optional[AxisScore]
    growth_a: Optional[AxisScore]
    expansion_a: Optional[AxisScore]
    camera_a: Optional[AxisScore]
    color_a: Optional[AxisScore]
    sound_a: Optional[AxisScore]

    # ⑧ Cross-Check 출력 (B채점 + 평균값)
    movement_final: Optional[AxisScore]
    growth_final: Optional[AxisScore]
    expansion_final: Optional[AxisScore]
    camera_final: Optional[AxisScore]
    color_final: Optional[AxisScore]
    sound_final: Optional[AxisScore]

    # ⑨ Grade Calculator 출력
    grade: Optional[Literal['strong', 'medium', 'weak']]
    weakest_axis: Optional[str]
    total_score: Optional[float]

    # ⑩ Embedder 출력
    embedding: Optional[list[float]]   # 1536차원

    # 메타
    errors: list[str]
    started_at: Optional[str]
    completed_at: Optional[str]
```

# 노드 구현 명세

## ② Movement Judge — 프롬프트 예시 (prompts.py)

```python
MOVEMENT_JUDGE_PROMPT = """당신은 슈퍼센트 크리에이티브팀의 광고 영상 분석 전문가입니다.
Annie의 '실패없는 크리에이티브 기획 바이블'에 정의된 6축 중
**움직임(Movement) 축만** 평가해주세요.

# 움직임 축의 정의
"한눈에 눈길을 끄는 변화 — 튕기고, 무너지고, 쏟아지는 장면.
짧고 강한 물리적 반응은 그 자체로 후킹 요소가 되고, 초반 유저를 빠르게 몰입시킵니다."

# 평가 지침
- 다른 축(성장/확장/카메라/컬러/사운드)에 대해서는 평가하지 마세요.
- 움직임 축만 1~5점으로 평가하고, 평가 근거를 추출 프레임 또는 스크립트에서 직접 인용하세요.
- 가설형 표현 사용: "...일 가능성", "...로 추정"
- 단정형 표현 금지: "이 영상은 ~다", "확실히 ~다"

# 입력 데이터
영상 장르: {genre}
스크립트: {script}
프레임 5장 첨부

# 출력 형식 (JSON)
{
  "score": 1~5 사이 숫자,
  "rationale": "1~2문장 평가 근거 (프레임/스크립트 인용 포함)",
  "confidence": 0.0~1.0
}
"""
```

나머지 5개 Judge 노드(③~⑦)도 같은 패턴.
각각 GROWTH_JUDGE_PROMPT, EXPANSION_JUDGE_PROMPT, CAMERA_JUDGE_PROMPT,
COLOR_JUDGE_PROMPT, SOUND_JUDGE_PROMPT를 prompts.py에 작성.
각 프롬프트는 Annie 글의 해당 축 정의를 그대로 인용.

## ⑧ Cross-Check 프롬프트

```python
CROSS_CHECK_PROMPT = """당신은 슈퍼센트 크리에이티브팀의 광고 영상 분석 전문가입니다.
아래 영상을 6축으로 평가하되, **반드시 다음 순서로** 평가하세요:
1. 사운드 → 2. 컬러 → 3. 카메라 → 4. 확장 → 5. 성장 → 6. 움직임

(앞선 축의 점수가 뒤 축에 영향을 주지 않도록 각 축을 독립적으로 판단하세요.)

# 6축 정의
[Annie 글의 6축 정의 그대로 인용]

# 입력 데이터
[프레임 + 스크립트 + 장르]

# 출력 형식 (JSON)
{
  "sound": {"score": ..., "rationale": "...", "confidence": ...},
  "color": {...},
  "camera": {...},
  "expansion": {...},
  "growth": {...},
  "movement": {...}
}
"""
```

## ⑨ Grade Calculator (LLM 호출 없음)

```python
def grade_calculator_node(state):
    scores = {
        'movement': state['movement_final']['score'],
        'growth': state['growth_final']['score'],
        'expansion': state['expansion_final']['score'],
        'camera': state['camera_final']['score'],
        'color': state['color_final']['score'],
        'sound': state['sound_final']['score'],
    }
    min_score = min(scores.values())
    total = sum(scores.values())
    weakest = min(scores, key=scores.get)

    if min_score >= 4 and total >= 24:
        grade = 'strong'
    elif min_score >= 3 and total >= 18:
        grade = 'medium'
    else:
        grade = 'weak'

    return {
        'grade': grade,
        'weakest_axis': weakest,
        'total_score': total
    }
```

# Graph 빌더 (graph/builder.py)

```python
from langgraph.graph import StateGraph, START, END

def build_centlens_graph():
    graph = StateGraph(CentLensState)

    # 노드 등록
    graph.add_node("preprocessor", preprocessor_node)
    graph.add_node("movement_judge", movement_judge_node)
    graph.add_node("growth_judge", growth_judge_node)
    graph.add_node("expansion_judge", expansion_judge_node)
    graph.add_node("camera_judge", camera_judge_node)
    graph.add_node("color_judge", color_judge_node)
    graph.add_node("sound_judge", sound_judge_node)
    graph.add_node("cross_check", cross_check_node)
    graph.add_node("grade_calculator", grade_calculator_node)
    graph.add_node("embedder", embedder_node)

    # 엣지: Preprocessor → 6개 Judge 병렬
    graph.add_edge(START, "preprocessor")
    graph.add_edge("preprocessor", "movement_judge")
    graph.add_edge("preprocessor", "growth_judge")
    graph.add_edge("preprocessor", "expansion_judge")
    graph.add_edge("preprocessor", "camera_judge")
    graph.add_edge("preprocessor", "color_judge")
    graph.add_edge("preprocessor", "sound_judge")

    # 엣지: 6개 Judge → Cross-Check (모두 완료 후 진행)
    graph.add_edge("movement_judge", "cross_check")
    graph.add_edge("growth_judge", "cross_check")
    graph.add_edge("expansion_judge", "cross_check")
    graph.add_edge("camera_judge", "cross_check")
    graph.add_edge("color_judge", "cross_check")
    graph.add_edge("sound_judge", "cross_check")

    # 엣지: Cross-Check → Grade → Embedder → END
    graph.add_edge("cross_check", "grade_calculator")
    graph.add_edge("grade_calculator", "embedder")
    graph.add_edge("embedder", END)

    return graph.compile()
```

# Streamlit 페이지 명세
[페이지 1, 2, 3 구현 명세 — 위 04_prototyping_plan.md 참조]

# Supabase 스키마
[전체 스키마 — 위 04_prototyping_plan.md 참조]

# UI/UX 원칙
- 한국어 UI 기본
- 등급별 컬러: 우수(녹색 #10b981) / 보통(노란색 #f59e0b) / 약함(회색 #6b7280)
- 가설 표시 시 "AI 가설" 뱃지로 시각적 분리
- LangGraph의 astream_events()로 노드별 진행 상황 실시간 시각화
- 슈퍼센트 브랜드 톤 (차분한 블루/네이비 계열)

# 코드 품질 요구사항
- 모든 외부 API 호출에 try-except + 사용자 친화적 에러 메시지
- LLM 호출은 재시도 로직 포함 (최대 2회)
- 프롬프트는 prompts.py에 중앙화
- 함수 단위 docstring 한국어로 작성
- 타입 힌트 필수
- LangGraph 노드는 모두 async (병렬 실행 위해)
- 노드별 실행 시간 측정 → node_traces 테이블에 저장

# 출력
1. 위 디렉토리 구조의 모든 파일을 빠짐없이 작성
2. requirements.txt 포함
3. README.md에 다음 포함:
   - 로컬 실행 방법
   - Streamlit Cloud 배포 방법
   - LangGraph 노드 구조 다이어그램
   - 각 노드의 책임 설명
4. 6축 루브릭 프롬프트는 Annie 글 표현 그대로 사용
5. 데모 캐시 5편 분량의 더미 데이터 JSON 포함

코드만 출력하고, 설명이나 주석은 코드 내부에 docstring으로 포함시키세요.
````

---

## 다음 문서

→ [아키텍처](architecture.md)
