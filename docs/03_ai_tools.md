# 03. AI 도구

## 기술 스택

| 도구 | 역할 | 선택 이유 |
|---|---|---|
| **Claude Sonnet 4.5** (Anthropic API) | 영상 프레임 멀티모달 분석 + 6축 루브릭 채점 + 근거 생성 | 멀티모달 + 한국어 생성 품질. 지원자의 BenchMate 프로젝트에서 A/B 양방향 교차 채점으로 Position Bias 제거 검증됨 |
| **OpenAI Whisper API** | 영상 나레이션 STT 추출 | 사운드 축 평가에 나레이션 텍스트 필요 |
| **OpenAI Embeddings** (text-embedding-3-small) | 신규 영상과 누적 자산의 시맨틱 유사도 계산 | 경쟁사 벤치마킹 시 "이 영상과 비슷한 우리 영상" 검색, 누적 자산의 자연어 검색 |
| **Supabase** (PostgreSQL + pgvector) | 영상 메타데이터 + 6축 점수 + 마케터 코멘트 + 임베딩 통합 DB | 메타데이터 필터 + 시맨틱 검색 통합. 지원자의 BenchMate 프로젝트에서 검증된 스택 |
| **ffmpeg** | 영상 프레임 시퀀스 추출 (0% / 5% / 25% / 50% / 95%) | 표준 도구 |
| **LangGraph** | 멀티에이전트 오케스트레이션 | 6축 평가의 축 독립성 보장 + 병렬 실행 |
| **Streamlit** | 마케터 UI (멀티페이지) | 빠른 프로토타이핑 + 파일 업로드 + 카드 UI. 지원자의 BenchMate 프로젝트에서 7화면 UI 검증됨 |

---

## 아키텍처 핵심 결정

### 1. LangGraph 기반 멀티에이전트 — 6축을 6개 독립 Judge 노드로 분리

**문제**: 같은 프롬프트에 6축을 한 번에 묻는 단일 호출 방식은 한 축의 점수가 다른 축에 영향을 주는 일관성 편향(consistency bias)이 생긴다. Claude가 "이 영상은 움직임이 강한데 그러니 카메라도 비슷한 점수로 줘야겠다"는 식의 패턴을 학습할 위험.

**해결**: 6개 Judge 노드로 분리. 각 노드는 자기 축만 평가하며, 다른 축의 점수나 근거를 컨텍스트에 넣지 않는다.

**부수 효과**: 6개 노드를 LangGraph의 병렬 분기로 동시 실행 → 1편당 처리 시간 단축 (직렬 12~18초 → 병렬 3~5초).

상세 설계: [architecture.md](architecture.md)

### 2. A/B 양방향 교차 채점

**문제**: LLM이 한 축의 평가를 끝낸 직후 다음 축을 평가하면, 직전 점수에 영향을 받는 Position Bias가 발생한다.

**해결**: Cross-Check 노드에서 1차 채점(A: 움직임→성장→확장→카메라→컬러→사운드)과 역순 재채점(B: 사운드→컬러→카메라→확장→성장→움직임)의 평균값을 사용.

**검증 근거**: 지원자의 BenchMate 프로젝트(LangGraph 11노드 기반 LLM 평가 플랫폼)에서 동일 방식으로 Position Bias 제거 효과 검증됨.

### 3. LLM 출력 가설형 표현 강제

**문제**: AI 진단이 마케터의 판단을 압도하는 단정형 표현("이 영상은 ~다")은 슈퍼센트가 명시한 "human oversight" 철학에 어긋난다.

**해결**: 모든 Judge 노드 프롬프트에 가설형 표현 강제.

- 사용: "...일 가능성", "...로 추정", "...할 수 있음"
- 금지: "확실히 ~다", "이 영상은 ~다"

UI에서도 AI 출력에는 "AI 가설" 뱃지를 부여하여 마케터의 최종 결정과 시각적으로 분리.

### 4. 6축 평가 시 축 간 독립성 유지

각 Judge 노드 프롬프트에 다음을 명시:

- 자기 축만 평가하고, 다른 축에 대해서는 평가하지 말 것
- 평가 근거는 추출된 프레임 또는 STT 스크립트를 직접 인용할 것

특수 케이스:

| 노드 | 입력 |
|---|---|
| Movement Judge | 프레임 + STT |
| Growth Judge | 프레임 + STT |
| Expansion Judge | 프레임 + STT |
| Camera Judge | 프레임만 (스크립트 무시) |
| Color Judge | 프레임만 (스크립트 무시) |
| Sound Judge | STT + 프레임 (효과음 단서가 시각적으로 드러나는 경우) |

### 5. 결정론적 등급 산출

Grade Calculator 노드는 LLM 호출 없이 수식으로 등급 산출. 같은 점수에는 항상 같은 등급이 나오도록 보장.

```python
def calculate_grade(scores):
    min_score = min(scores.values())
    total = sum(scores.values())

    if min_score >= 4 and total >= 24:
        return "strong"
    elif min_score >= 3 and total >= 18:
        return "medium"
    else:
        return "weak"
```

---

## 비용 추정

영상 1편당 처리 비용 (대략):

| 항목 | 호출 횟수 | 단가 | 1편 비용 |
|---|---|---|---|
| Whisper STT (1분 영상 기준) | 1 | $0.006/min | $0.006 |
| Claude Sonnet 4.5 (Judge × 6) | 6 | ~$0.015/call | $0.090 |
| Claude Sonnet 4.5 (Cross-Check) | 1 | ~$0.020/call | $0.020 |
| OpenAI Embeddings | 1 | ~$0.0001 | $0.0001 |
| **합계** | — | — | **~$0.116** |

월 1,000편 분석 시 약 $116. 슈퍼센트 운영 규모(연 1억 달러 마케팅)와 비교하면 무시할 수준.

---

## 다음 문서

→ [04. 프로토타이핑 계획](04_prototyping_plan.md)
