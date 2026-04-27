# CentLens

> 슈퍼센트 자체 정의 평가 프레임(변화 3축 + 연출 3축)을 LLM 멀티모달로 자동 적용하여, 광고 컨텐츠 마케터·크리에이티브 디렉터의 광고 소재 분석 직무를 가속하는 분석 어시스턴트.

**제품명 의미**: Cent (슈퍼센트가 가장 작은 가치 단위로 삼는 것) × Lens (들여다보는 도구).
슈퍼센트가 자체 정의한 6축으로 광고 영상을 들여다보는 렌즈.

**슈퍼센트 AI 프로덕트 기획자 과제 전형 제출물** · 2026.04.30

---

## 한눈에 보기

| 항목 | 내용 |
|---|---|
| 영역 | 마케팅 — 광고 소재 분석 |
| 사용자 | 광고 컨텐츠 마케터, 크리에이티브 디렉터 |
| 핵심 가치 | 슈퍼센트 자체 평가 프레임의 LLM 자동화 |
| AI 아키텍처 | LangGraph 기반 멀티에이전트 (10개 노드) |
| 기술 스택 | Claude Sonnet 4.5 · Whisper · OpenAI Embeddings · Supabase · Streamlit |
| 운영 철학 | "data-driven insights + human oversight" (슈퍼센트 UA 운영 철학 인용) |

---

## 무엇을 해결하는가

### 슈퍼센트의 마케팅 운영 — 공식 출처 기반 사실

슈퍼센트는 다음과 같이 마케팅을 운영한다고 공식 출처에 명시되어 있다.

- **규모**: 연간 1억 달러(약 1,400억 원) 규모의 마케팅, 수백 개 크리에이티브 동시 제작·테스트 (한국경제 RE:BOUND 2025 보도자료)
- **사이클**: 2주마다 신규 크리에이티브 제작·테스트 (Pizza Ready UA 전략 글, 2025.05)
- **버전 수**: 한 게임당 30+ playable ad 버전 동시 운영 (동일 글)
- **자체 평가 프레임**: 변화 3축(움직임/성장/확장) + 연출 3축(카메라/컬러/사운드) (Annie, "실패없는 크리에이티브 기획 바이블", 2025.06)
- **운영 철학**: "data-driven insights with human oversight — 자동화 시스템에 통째로 맡기지 않음" (Pizza Ready 글)

### 직무 정의에 명시된 분석 업무

광고 컨텐츠 마케터 채용공고에 명시된 주요 업무:
- 광고 소재의 과거 성과 분석
- 신규 광고 소재 발굴
- 경쟁사 광고 소재 벤치마킹
- 시장 트렌드 분석

크리에이티브 디렉터 채용공고에 명시된 직무 요약:
> 광고 크리에이티브를 제작하고, 테스트하고, 분석하는 과정을 통해 시장성 높은 광고 크리에이티브를 발굴

### 본 도구가 다루는 영역

위 직무에 정의된 분석 업무에 슈퍼센트 자체 프레임(변화 3축 + 연출 3축)을 LLM 멀티모달로 자동 적용한다. AI는 점수와 근거를 산출하지만, 활용 결정은 마케터가 한다.

---

## 어떻게 해결하는가

### 1. 슈퍼센트 자체 루브릭을 그대로 차용

Annie 글에 정의된 6축을 평가 기준으로 사용한다. 자체 정의 표현을 변형 없이 인용.

| 축 | 정의 (Annie 글 인용) |
|---|---|
| 움직임 | 한눈에 눈길을 끄는 변화 — 튕기고, 무너지고, 쏟아지는 장면 |
| 성장 | 변화하는 플레이어 — 플레이어가 변화하는 장면 |
| 확장 | 넓어지는 공간, 변화하는 시스템 |
| 카메라 | 시점/슬로우/이동으로 정보 전달 |
| 컬러 | 메인 vs 배경 톤 대비, 위험·금지 색상 |
| 사운드 | 변화 순간 효과음, 리듬, 공간감 |

### 2. LangGraph 멀티에이전트 — 6축을 6개 독립 Judge 노드로 분리

같은 프롬프트에 6축을 한 번에 묻는 단일 호출 방식은 한 축의 점수가 다른 축에 영향을 주는 일관성 편향이 생긴다. 노드를 분리하면 각 Judge는 자기 축만 보므로 축 독립성이 보장된다.

![노드 다이어그램](docs/images/node_diagram.svg)

| 노드 | 역할 | LLM |
|---|---|---|
| ① Preprocessor | ffmpeg 프레임 추출 + Whisper STT | ❌ |
| ② Movement Judge | 움직임 축 평가 | ✅ |
| ③ Growth Judge | 성장 축 평가 | ✅ |
| ④ Expansion Judge | 확장 축 평가 | ✅ |
| ⑤ Camera Judge | 카메라 축 평가 | ✅ |
| ⑥ Color Judge | 컬러 축 평가 | ✅ |
| ⑦ Sound Judge | 사운드 축 평가 | ✅ |
| ⑧ Cross-Check | A/B 양방향 교차 채점 (Position Bias 제거) | ✅ |
| ⑨ Grade Calculator | weakest-link 등급 산출 | ❌ |
| ⑩ Embedder | 시맨틱 검색용 임베딩 생성 | ❌ |

병렬 실행으로 1편당 처리 시간 단축: 직렬 12~18초 → 병렬 3~5초.

### 3. 분석 대상 분류

채용공고 직무 정의에 맞춰 3개 분석 대상 모두 지원:
- **신규 광고 소재** — 사전 검토
- **경쟁사 광고 소재** — 벤치마킹
- **시장 트렌드** — 글로벌 탑 크리에이티브 분석

### 4. 누적 자산 + 시맨틱 검색

영상별 6축 점수, 마케터 코멘트, 분석 일자가 Supabase에 누적된다. 자연어 검색으로 과거 분석 자산을 빠르게 조회할 수 있다.

> 예: "확장 축이 강한 시뮬레이션 게임 영상", "사운드 약했던 경쟁사 영상"

이는 채용공고에 명시된 "광고 소재의 과거 성과를 분석하고 향후 실행 계획 수립" 업무에 직접 활용 가능한 데이터 자산이 된다.

---

## 데모

### 시연 시나리오

> "Annie 글이 분석한 5개 영상(Burger Please, Pizza Ready, Snake Clash, Twerk Race 3D, Kingshot)을 도구에 넣었을 때, AI 진단이 Annie의 평가와 어떻게 일치하는지"

이 영상들은 슈퍼센트 자체 블로그가 직접 6축 분석 사례로 사용한 영상이므로, **블로그 글 자체가 본 도구의 채점 정확도를 검증할 수 있는 reference**가 된다.

- 데모 영상 (Loom): _제출일 업로드 예정_
- 라이브 프로토타입 (Streamlit Cloud): _제출일 배포 예정_

---

## 빠른 시작

### 사전 준비

```bash
# Python 3.11+
python --version

# ffmpeg 설치 확인
ffmpeg -version

# yt-dlp 설치 (영상 다운로드용)
pip install yt-dlp
```

### 1. 저장소 클론 및 의존성 설치

```bash
git clone https://github.com/{your-username}/centlens.git
cd centlens
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env.example`을 `.env`로 복사하고 키를 채운다.

```bash
cp .env.example .env
```

```ini
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
```

### 3. Supabase 스키마 생성

Supabase SQL Editor에서 `centlens/schema.sql`을 실행한다.

### 4. 데이터 준비 (영상 다운로드 + 프레임 추출)

```bash
python scripts/prepare_data.py
```

이 스크립트는 다음 작업을 수행한다:
- 슈퍼센트 공식 광고 영상 5편 다운로드 (Burger Please, Pizza Ready, Snake Clash, Twerk Race 3D, Kingshot)
- 각 영상에서 5프레임 추출 (0% / 5% / 25% / 50% / 95%)
- Whisper API로 STT 추출
- `data/` 폴더에 저장

### 5. 데모 캐시 사전 생성 (선택)

```bash
python scripts/precompute_demo.py
```

5편 영상에 대해 6축 채점을 미리 실행하여 `demo_cache/`에 저장한다. 데모 시연 시 즉시 결과를 보여줄 수 있다.

### 6. 앱 실행

```bash
streamlit run centlens/app.py
```

브라우저가 자동으로 열린다 (기본 http://localhost:8501).

---

## 문서

기획 단계부터 구현까지 모든 의사결정을 문서화했다.

| 문서 | 내용 |
|---|---|
| [01. 문제 정의](docs/01_problem_definition.md) | 슈퍼센트 마케팅 운영 + 직무 정의 + 본 도구 영역 |
| [02. 해결 방법](docs/02_solution.md) | CentLens 제품 설명 + 핵심 기능 + 사용자 흐름 |
| [03. AI 도구](docs/03_ai_tools.md) | 기술 스택 + 선택 이유 + 아키텍처 결정 |
| [04. 프로토타이핑 계획](docs/04_prototyping_plan.md) | MVP 범위 + 입출력 + 검증 전략 |
| [05. 프로토타이핑 방법](docs/05_prototyping_method.md) | Day 1~4 일정 + 시연 캐싱 전략 |
| [06. 바이브코딩 프롬프트](docs/06_vibe_coding_prompt.md) | LangGraph 멀티에이전트 구현 명세 전문 |
| [아키텍처](docs/architecture.md) | LangGraph StateGraph 노드 다이어그램 + 책임 분리 |
| [화면 설계](docs/wireframes.md) | 와이어프레임 4장 + UX 흐름 |

---

## 기술 스택

### 핵심 의존성

| 도구 | 역할 |
|---|---|
| Python 3.11 | 런타임 |
| Streamlit | 멀티페이지 UI |
| LangGraph | 멀티에이전트 오케스트레이션 |
| Anthropic Claude Sonnet 4.5 | 영상 멀티모달 분석 + 6축 채점 |
| OpenAI Whisper | 영상 나레이션 STT |
| OpenAI Embeddings (text-embedding-3-small) | 시맨틱 검색용 벡터화 |
| Supabase (PostgreSQL + pgvector) | 메타데이터 + 임베딩 통합 DB |
| ffmpeg-python | 영상 프레임 시퀀스 추출 |

### 아키텍처 결정 핵심

- **A/B 양방향 교차 채점**: 같은 영상에 6축을 다른 순서로 두 번 채점, 평균값 사용 → Position Bias 제거
- **LLM 출력 가설형 표현 강제**: "...일 가능성", "...로 추정" — AI가 마케터의 판단을 압도하지 않도록
- **6축 평가 시 축 간 독립성 유지**: 한 축 평가 시 다른 축 정보를 컨텍스트에 넣지 않음

---

## 출처 — 인용된 슈퍼센트 자료

본 기획은 슈퍼센트 공식 출처에서 직접 확인된 사실로만 구성되었다. 추론은 일체 사용하지 않았다.

### 슈퍼센트 공식 블로그 (Medium)

1. [Annie. "⚡️실패없는 크리에이티브 기획 바이블" (2025.06.10)](https://medium.com/supercent-blog/%EF%B8%8F%EC%8B%A4%ED%8C%A8%EC%97%86%EB%8A%94-%ED%81%AC%EB%A6%AC%EC%97%90%EC%9D%B4%ED%8B%B0%EB%B8%8C-%EA%B8%B0%ED%9A%8D-%EB%B0%94%EC%9D%B4%EB%B8%94-f6ba35e4753c) — 변화 3축 + 연출 3축 자체 정의
2. [Riley. "🍕 Pizza Ready's Path to 200M Downloads: Inside Supercent's UA Strategy" (2025.05)](https://medium.com/supercent-blog/pizza-readys-path-to-200m-downloads-inside-supercent-s-ua-strategy-addbd96dcd21) — Demand-driven 마케팅 + 30+ 버전 + 2주 사이클 + Human Oversight 철학
3. [Seyoung. "버거플리즈 차트 역주행의 비밀" (2023.07)](https://medium.com/supercent-blog/%EB%B2%84%EA%B1%B0%ED%94%8C%EB%A6%AC%EC%A6%88-%EC%B0%A8%ED%8A%B8-%EC%97%AD%EC%A3%BC%ED%96%89%EC%9D%98-%EB%B9%84%EB%B0%80-eeee5ae306fd) — 매뉴얼 작업의 어려움
4. [Kyuyoung Kim. "전환율을 높이는 ASO 스크린샷 최적화 TIP 6" (2023.11)](https://medium.com/supercent-blog/%EC%A0%84%ED%99%98%EC%9C%A8%EC%9D%84-%EC%98%AC%EB%A6%AC%EB%8A%94-aso-%EC%8A%A4%ED%81%AC%EB%A6%B0%EC%83%B7-%EC%B5%9C%EC%A0%81%ED%99%94-tip-6-1a3ece629db2)
5. [Kyuyoung Kim. "다운로드를 유도하는 아이콘 만드는 방법 5가지" (2023.09)](https://medium.com/supercent-blog/%EB%8B%A4%EC%9A%B4%EB%A1%9C%EB%93%9C%EB%A5%BC-%EC%9C%A0%EB%8F%84%ED%95%98%EB%8A%94-%EC%95%84%EC%9D%B4%EC%BD%98-%EB%A7%8C%EB%93%9C%EB%8A%94-%EB%B0%A9%EB%B2%95-5%EA%B0%80%EC%A7%80-b70dff9282e3)
6. [Seohee. "광고 수익화 완전 정복: LTV 최적화의 기술" (2023.07)](https://medium.com/supercent-blog/%EA%B4%91%EA%B3%A0-%EC%88%98%EC%9D%B5%ED%99%94-%EC%99%84%EC%A0%84%EC%A0%95%EB%B3%B5-ltv%EC%B5%9C%EC%A0%81%ED%99%94%EC%9D%98-%EA%B8%B0%EC%88%A0-55963d1fc7bb)
7. [Supercent.official. "Hit & Run: Solo Leveling — 2022년 GameAnalytics가 선정한 글로벌 탑 게임이 되기까지" (2023.07)](https://medium.com/supercent-blog/hit-run-solo-leveling-2022%EB%85%84-gameanalytics%EA%B0%80-%EC%84%A0%EC%A0%95%ED%95%9C-%EA%B8%80%EB%A1%9C%EB%B2%8C-%ED%83%91-%EA%B2%8C%EC%9E%84%EC%9D%B4-%EB%90%98%EA%B8%B0%EA%B9%8C%EC%A7%80-73dd9b1ed6c2)
8. [Supercent.official. "광고수익화 실무 꿀팁 대방출" (2023.07)](https://medium.com/supercent-blog/%EA%B4%91%EA%B3%A0%EC%88%98%EC%9D%B5%ED%99%94-%EC%8B%A4%EB%AC%B4-%EA%BF%80%ED%8C%81-%EB%8C%80%EB%B0%A9%EC%B6%9C-9af5ad637db1)

### 채용공고

- [모바일 게임 광고 컨텐츠 마케터 (원티드)](https://www.wanted.co.kr/wd/122558) — 직무 주요 업무
- 크리에이티브 디렉터 (슈퍼센트 채용 페이지) — 직무 요약

### 기업 자료

- [한국경제. "슈퍼센트, 리퍼블리싱 프로그램 RE:BOUND 2025 진행…총 상금 140억 원 규모" (2025.10.01)](https://www.hankyung.com/article/202509308015O)
- [슈퍼센트 공식 사이트 (corp.supercent.io)](http://corp.supercent.io)

---

## 라이선스

본 저장소는 슈퍼센트 AI 프로덕트 기획자 과제 전형 제출용으로 작성되었다.

코드: MIT License
문서·기획: All rights reserved (저자: 곽승연 / Grace)

---

## 작성자

**곽승연 (Grace Kwak)**
- 슈퍼센트 AI 프로덕트 기획자 지원자
- GitHub: [@devfyoo2829-lab](https://github.com/devfyoo2829-lab)
- 제출일: 2026.04.30
