# 04. 프로토타이핑 계획

## 프로토타입 목적

다음 3가지를 End-to-End로 검증한다.

1. 영상 업로드 → 6축 자동 분해까지 안정 동작
2. 6축 점수와 근거가 Annie 글에 정의된 자체 프레임 언어로 일관되게 출력
3. 신규/경쟁사/트렌드 분류로 누적된 데이터가 검색·비교 가능한 형태로 저장됨

본 프로토타입은 **UX 흐름의 작동성**을 검증하는 것이 목적이다. 모델 정확도(실제 CTR/ROAS와의 상관)는 사내 데이터 연동 단계에서 검증.

---

## 구현 범위

### MVP에 포함

- 영상 업로드 (파일 또는 URL, 최대 10편)
- 분류 태그 (신규/경쟁사/트렌드) + 게임명 + 장르
- 프레임 추출 + Whisper STT
- LangGraph 멀티에이전트 (10개 노드)
- Claude 6축 루브릭 채점 (각 축별 독립 Judge 노드)
- A/B 양방향 교차 채점
- weakest-link 종합 등급 산출
- 영상 상세 화면 (6축 게이지 + 추출 프레임 + 근거 텍스트)
- 마케터 코멘트 입력
- 누적 영상 검색·필터 (게임/장르/분류/축별 점수/시맨틱 검색)
- 노드 실행 트레이스 (영상 상세 페이지에서 펼침)

### MVP 제외 (확장 범위로 명시)

- 광고 플랫폼 직접 연동 (Meta Ads, Unity Ads 등)
- 실제 ROAS/CPI 데이터 자동 수집·연결
- 다중 사용자 협업
- Slack 알림 연동
- 크리에이터 피드백 자동 회신

---

## 사용할 도구

```
Python 3.11
+ Streamlit (멀티페이지 UI)
+ LangGraph (멀티에이전트 오케스트레이션)
+ Anthropic SDK (Claude Sonnet 4.5)
+ OpenAI SDK (Whisper + Embeddings)
+ Supabase Python Client (PostgreSQL + pgvector)
+ ffmpeg-python
```

배포: **Streamlit Cloud** (무료 티어로 데모 링크 즉시 공유 가능)

---

## 입력 데이터

분석 대상이 될 광고 영상은 슈퍼센트 공식 채널에서 공개된 영상으로 한정한다.

Annie 글에서 직접 분석 사례로 사용된 게임의 공식 마케팅 영상을 데이터로 사용:

> Burger Please, Pizza Ready, Snake Clash, Twerk Race 3D, Kingshot

— Annie, "⚡️실패없는 크리에이티브 기획 바이블", 2025.06.10

### 검증 전략 — Annie 글 자체가 Reference

이 게임들은 Annie 글이 이미 6축으로 분석한 영상이므로, **블로그 글 자체가 본 도구의 채점 기준이 슈퍼센트의 실제 평가 기준과 일치하는지 검증할 수 있는 reference**가 된다.

예를 들어 Annie 글에 다음 내용이 있다.

> Burger Please의 크리에이티브를 먼저 살펴보면, 모두의 시선을 사로잡을 만큼 거대한 고기 덩어리를 톱날로 자르니 셀 수 없을 만큼의 햄버거가 한꺼번에 쏟아집니다. 절단 움직임과 대량의 오브젝트가 결합되어 강한 시각적 자극을 만들어냅니다.

→ 본 도구의 Movement Judge가 Burger Please 영상을 분석했을 때 "절단 움직임 + 대량 오브젝트 + 강한 시각 자극"이라는 평가를 일관되게 내놓는지 확인하면, 도구의 채점 기준이 슈퍼센트의 실제 평가 기준과 정렬되어 있는지 검증할 수 있다.

---

## 출력 방식

### 우선순위 큐 화면 (페이지 1: 업로드 및 분석 → 결과)

- 누적된 영상이 분류·등급·점수 필터로 정렬된 카드 리스트
- 카드 정보: 썸네일 + 게임명 + 종합 점수 + 등급 뱃지(녹색/노란색/회색) + 가장 약한 축
- 등급별 그룹핑: 우수 / 보통 / 약함

### 영상 상세 화면 (페이지 2)

- 영상 플레이어 + 메타데이터
- 6축 점수 게이지 + 축별 근거 텍스트 + 추출 프레임 5장
- weakest-link 종합 등급 + 가장 약한 축
- **노드 실행 트레이스** (확장 영역) — 각 노드의 실행 시간, 입출력 토큰, A/B 점수 비교
- 마케터 코멘트 입력

### 누적 데이터 화면 (페이지 3)

- 자연어 검색 (시맨틱 검색)
- 통계 (분류별/게임별/축별 평균)
- 필터 (게임/장르/분류/축별 점수 범위/기간)
- 카드 리스트

---

## Supabase 스키마

```sql
create extension if not exists vector;

create table videos (
  id uuid primary key default gen_random_uuid(),
  category text check (category in ('new', 'competitor', 'trend')),
  game_name text not null,
  genre text not null,
  uploaded_at timestamptz default now(),
  video_path text,
  script text,
  embedding vector(1536)
);

create table axis_scores (
  id uuid primary key default gen_random_uuid(),
  video_id uuid references videos(id) on delete cascade,
  axis text check (axis in ('movement','growth','expansion','camera','color','sound')),
  score_a numeric check (score_a >= 1 and score_a <= 5),
  score_b numeric check (score_b >= 1 and score_b <= 5),
  score_final numeric check (score_final >= 1 and score_final <= 5),
  rationale text,
  confidence numeric
);

create table grades (
  id uuid primary key default gen_random_uuid(),
  video_id uuid references videos(id) on delete cascade,
  grade text check (grade in ('strong','medium','weak')),
  weakest_axis text,
  total_score numeric
);

create table marketer_comments (
  id uuid primary key default gen_random_uuid(),
  video_id uuid references videos(id) on delete cascade,
  comment text,
  override_reason text,
  created_at timestamptz default now()
);

create table node_traces (
  id uuid primary key default gen_random_uuid(),
  video_id uuid references videos(id) on delete cascade,
  node_name text,
  duration_ms integer,
  input_tokens integer,
  output_tokens integer,
  status text,
  error_message text,
  executed_at timestamptz default now()
);
```

`node_traces` 테이블은 LangGraph 실행 흔적을 저장 — 영상 상세 페이지에서 노드별 실행 시간/토큰을 시각화하는 데 사용. 면접 시연에서 시스템의 내부 동작을 설명하는 데도 활용.

---

## 다음 문서

→ [05. 프로토타이핑 방법](05_prototyping_method.md)
