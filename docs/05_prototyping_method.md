# 05. 프로토타이핑 방법

실제 제작 흐름을 시간순으로 정리한다 (4월 27일 ~ 30일, 4일).

---

## Day 1 (4/27, 일) — 데이터 준비 + 루브릭 프롬프트 설계

### 작업 항목

1. **Annie 글 6축 정의를 그대로 인용해 프롬프트 작성** (`centlens/core/prompts.py`에 중앙화)
2. **Annie 글이 분석한 5개 게임의 슈퍼센트 공식 영상 다운로드**
   - Burger Please
   - Pizza Ready
   - Snake Clash
   - Twerk Race 3D
   - Kingshot
3. **ffmpeg로 5프레임 추출** (각 영상에서 0% / 5% / 25% / 50% / 95% 시점)
4. **Whisper로 나레이션 STT 추출**
5. **Supabase 스키마 생성 + 메타데이터/프레임 경로/STT 저장**

### 산출물

- `scripts/prepare_data.py` 실행 완료
- `data/videos/*.mp4` (5편)
- `data/frames/{video_id}/{0..4}.jpg` (25개 프레임)
- `data/scripts/{video_id}.txt` (5개 STT)
- Supabase `videos` 테이블에 5개 row

---

## Day 2 (4/28, 월) — 핵심 파이프라인

### 작업 항목

1. **LangGraph StateGraph 빌더 작성** (`centlens/graph/builder.py`)
2. **State 정의** (`centlens/graph/state.py`)
3. **10개 노드 구현** (`centlens/graph/nodes/*.py`)
   - Preprocessor (ffmpeg + Whisper 호출)
   - Movement / Growth / Expansion / Camera / Color / Sound Judge (각각 독립)
   - Cross-Check (A/B 양방향 교차 채점)
   - Grade Calculator (수식 계산)
   - Embedder (OpenAI Embeddings)
4. **Streamlit 멀티페이지 구조 생성**
5. **Supabase CRUD 함수 작성** (`centlens/core/repository.py`)

### 산출물

- LangGraph 그래프가 5편 영상에 대해 End-to-End 동작 확인
- Supabase에 6축 점수 + 등급 + 임베딩 저장 확인

---

## Day 3 (4/29, 화) — UI 다듬기 + 데모 데이터 시연 준비

### 작업 항목

1. **영상 상세 페이지** — 6축 게이지 + 프레임 + 근거 텍스트 + 노드 트레이스
2. **누적 데이터 페이지** — 검색·필터 + 카드 리스트 + 통계
3. **마케터 코멘트 영역** + 의사결정 사유 입력
4. **시연 캐싱 전략 적용**
5. **와이어프레임 4장 정리** (`docs/wireframes.md`)

### 시연 캐싱 전략

영상 멀티모달 처리는 1편당 5~10초 소요 (병렬 실행 시). 데모에서 시간 끌리지 않도록:

- **5편(Annie 글 분석 영상)은 사전 처리된 결과 캐시로 즉시 표시**
- **1편은 즉석 분석 시연** (실제 동작 보여주기 위함)

```bash
python scripts/precompute_demo.py
```

이 스크립트가 5편 영상에 대해 LangGraph 전체 흐름을 실행하고 결과를 `demo_cache/*.json`에 저장. 앱 시작 시 캐시를 Supabase에 자동 로드.

### 산출물

- 3개 페이지 모두 동작 확인
- `demo_cache/*.json` 5개 파일 생성
- 와이어프레임 4장 PNG/SVG

---

## Day 4 (4/30, 수) — 데모 + 배포 + 제출

### 작업 항목

1. **Streamlit Cloud 배포** → 공개 링크 확보
2. **Loom 데모 영상 녹화** (2분, 시나리오 아래)
3. **GitHub 저장소 정리** — README + docs + scripts + 코드
4. **22시 이전 제출** (서버/네트워크 버퍼 1시간)

### 데모 시나리오 (2분)

> "Annie 글이 분석한 5개 영상을 도구에 넣었을 때, AI 진단이 Annie의 평가와 어떻게 일치하는지"

**0:00~0:20** 인트로
- CentLens 소개 한 줄
- 슈퍼센트 운영 철학 ("data-driven insights + human oversight") 인용
- 직무 정의에 명시된 분석 업무 4종 언급

**0:20~0:50** 신규 영상 업로드 + 분석
- Annie 글에 등장하지 않는 새 영상 1편 업로드
- LangGraph 노드 진행 상황 실시간 시각화 (① → ②~⑦ 병렬 → ⑧ → ⑨ → ⑩)
- 결과 화면 — 6축 점수 + 근거 + weakest-link 등급

**0:50~1:30** Annie 글 검증 시연
- 사전 캐시된 5편 영상 큐 화면 표시
- Pizza Ready 영상 클릭 → 6축 점수 확인
- Annie 글의 평가 ("유리병을 굴려 깨뜨리는 순간 안에 담긴 오브젝트들이 한번에 쏟아집니다")와 도구의 Movement 축 진단 비교
- 노드 실행 트레이스 펼쳐서 A/B 점수 차이 보여주기

**1:30~1:50** 누적 자산 + 시맨틱 검색
- 누적 데이터 페이지 이동
- "확장 축이 강한 영상" 자연어 검색 시연
- 분류별 통계 표시

**1:50~2:00** 마무리
- 채용공고 직무 정의에 직접 매핑되는 4가지 활용 방법 요약
- 확장 로드맵 (실제 ROAS 연동 → 가중치 자동 튜닝)

### 산출물

- Streamlit Cloud 공개 링크
- Loom 데모 영상 (공유 가능 링크)
- GitHub 저장소 (public)
- 과제 문서 PDF

---

## 일정 요약

| 날짜 | 핵심 작업 | 검증 포인트 |
|---|---|---|
| 4/27 (일) | 데이터 준비 + 프롬프트 설계 | 5편 영상에서 프레임/STT 추출 완료 |
| 4/28 (월) | LangGraph 파이프라인 + UI 골격 | End-to-End 1편 처리 동작 |
| 4/29 (화) | UI 완성 + 데모 캐시 | 3페이지 모두 동작 + 캐시 5편 |
| 4/30 (수) | 배포 + 데모 영상 + 제출 | 22시 이전 제출 |

---

## 다음 문서

→ [06. 바이브코딩 프롬프트](06_vibe_coding_prompt.md)
