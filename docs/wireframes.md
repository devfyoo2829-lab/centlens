# CentLens 화면 설계

광고 컨텐츠 마케터·크리에이티브 디렉터를 사용자로 가정한 한국어 인터페이스. 3페이지 멀티페이지 Streamlit 앱.

> 시각 명세(다크 톤 HTML 시안 + 30개 툴팁): [`docs/wireframes/`](wireframes/) 참조.
> ASCII 와이어프레임 v1: [`docs/wireframes_v1_ascii.md`](wireframes_v1_ascii.md)

---

## 페이지 구조

| URL | 파일 | 라벨 | 매핑되는 직무 활동 |
|---|---|---|---|
| `/analyze` | `pages/1_analyze.py` | 새 영상 분석 | 신규 광고 소재 발굴, 경쟁사 광고 소재 벤치마킹, 시장 트렌드 분석 |
| `/detail` | `pages/2_detail.py` | 영상 상세 | 광고 크리에이티브 분석 |
| `/archive` | `pages/3_archive.py` | 분석한 영상 모음 | 광고 소재의 과거 성과 분석 |

진입 시 `app.py` → `pages/1_analyze.py`로 자동 라우팅 (광고 사전 분석 도구로서 첫 화면이 입력 폼).

---

## 페이지 1 — `/analyze` (새 영상 분석)

### 구성

- **소개 카드** (`.cl-intro-card`, 라벤더 톤)
  - 헤딩: "광고 집행 전, 6축으로 먼저 점검합니다"
  - 본문: CentLens는 슈퍼센트의 광고 사전 분석 도구. 6축(움직임·성장·확장·카메라·컬러·사운드) 30~40초 진단.
  - 비용 안내: API 비용 $0.05~$0.10/편. 시연 권장: "기존 영상 재분석" 옵션.
- **영상 입력 (좌측 컬럼)** — 3가지 옵션
  - A. 파일 업로드 (`st.file_uploader`, MP4 ≤ 200MB)
  - B. YouTube URL (`st.text_input`)
  - C. 기존 영상 재분석 (`st.selectbox`, 시드 5편 + 기존 분석 영상)
- **분류 + 메타 (우측 컬럼)**
  - 분류 3버튼: 자사 신규 / 경쟁사 / 시장 트렌드 (active=primary, 비활성=secondary)
  - 게임명 / 장르 (텍스트 입력)
  - 옵션 C 선택 시 메타 자동 동기화 (`session_state`)
- **분석 시작** (primary 버튼, full width)
- **같은 영상 검증** (분기 밖, `pending_match` 보존 패턴)
  - SHA-256 해시로 동일 영상 매칭 — 매칭 시 카드 + `[기존 결과 보기]`/`[강제 재분석]` 두 버튼
- **분석 진행 상황** (10노드 LangGraph 실시간)
  - ① 영상 준비 (Whisper STT) → ②~⑦ 6축 평가 (병렬) → ⑧ 교차 검증 → ⑨ 등급 산출 → ⑩ 검색 인덱싱
  - `astream(stream_mode="updates")` + placeholder 실시간 갱신

### 핵심 인터랙션
- 분석 완료 시 자동으로 `/detail?slug=...`로 라우팅 (`session_state["nav_slug"]` + `query_params` 백업 채널)
- 시드 영상 URL은 `_match_seed_video()`로 yt-dlp 우회 → 로컬 mp4 즉시 사용
- 외부 YouTube URL 다운로드 실패 시 사용자 친화적 안내 (시드 5편 URL + 옵션 ②③ 제안)

---

## 페이지 2 — `/detail` (영상 상세)

### 구성

- **뒤로가기 링크**: "분석한 영상 모음 →" (`/archive`로 anchor)
- **헤더**: 게임명 + 분류 뱃지 + 종합 등급 뱃지 (강함/보통/약함 컬러 분기)
- **영상 + 추출 5장면 카드**
  - 좌측 영상 플레이어 (`st.video`, 파일 없으면 `cl-fallback` 안내)
  - 우측 5프레임 (0%/5%/25%/50%/95% 시점, base64 인라인)
- **6축 평가 헤더** + "가장 약한 축" 표시 (weakest-link 기준)
- **변화 3축 카드** (라벤더 #a78bfa) — 움직임 / 성장 / 확장
  - 각 축: 한글 이름 + tooltip + `1차 X.XX · 검증 X.XX` + final 점수 + 게이지 바
  - `|A−B| ≥ 1.0`인 축은 "관점 차이 큼" 뱃지 (앰버)
- **연출 3축 카드** (민트 #34d399) — 카메라 / 컬러 / 사운드
- **관점 차이 분석 카드** (앰버 톤, `cl-divergence-card`)
  - `|A−B|` 가장 큰 축 자동 선정 (다양한 케이스에서 1.0~2.2 분포)
  - 1차 평가(독립 6 Judge) vs 교차 검증(역순 6축 일괄) rationale 비교 좌우 분할
- **분석 단계별 시간** — 10노드 duration grid + 총 처리 시간
- **마케터 코멘트** — `st.text_area` (현재 세션 내 임시 저장, 추후 Supabase)

### 빈 상태
slug 누락 또는 매칭 실패 시 `cl-empty-state` 카드 + `[새 영상 분석]` / `[분석한 영상 모음]` 두 액션 버튼.

---

## 페이지 3 — `/archive` (분석한 영상 모음)

### 구성

- **헤더**: 페이지 타이틀 + 카운트(자사 N / 경쟁사 N / 트렌드 N) + `시드 복원` 버튼 + `삭제된 영상 보기` 토글
- **의미 검색** (페이지 상단으로 lift)
  - 텍스트 input (`_search_input` 임시 키 + `on_change=_commit_search` Enter commit)
  - `[찾기]` 버튼 (`on_click=_commit_search`)
  - 예시 칩 3개 ("사운드가 약했던 경쟁사 영상" 등) — `on_click` 콜백
- **검색 활성 시** (`active_query` truthy):
  - 컴팩트 결과 카드 5편 (`cl-search-result-card`) — 썸네일 X, 미니 바 + 유사도 뱃지(라벤더) + 상세 보기
  - 헤더 옆 + 결과 하단 양쪽에 `[← 전체 영상 보기]` 버튼
  - `st.stop()`으로 통계/6축/필터/그리드 모두 차단
- **검색 비활성 시** (활성 분기 통과 후만 노출):
  - **통계 4카드**: 전체 영상 수 / 평균 총점 / 가장 잘된 축 / 가장 약한 축
  - **6축 레이더 차트** (Plotly) — 5편 final 점수 겹쳐 비교
    - 자사 신규 = 라벤더 ramp / 경쟁사 = 민트 ramp
    - 우측 인사이트: 공통 약점 / 가장 강한 축 / 자사 vs 경쟁사 gap
  - **필터** (multiselect 3종): 분류 / 등급 / 장르
  - **카드 그리드** (2 컬럼): 분류 뱃지 + 게임명 + 등급 + 썸네일 + 6축 미니 + `[자세히 보기]` + `🗑`
- **카드 삭제** — `@st.dialog` 모달 + 영구 삭제 체크박스 (soft delete 기본, `data/.trash/{slug}/` 이동)
- **삭제된 영상 섹션** (토글 ON 시) — 회색 톤 카드 + `↩ 복원` / `🗑 영구 삭제`

---

## 디자인 토큰 (요약)

자세한 명세: [`docs/wireframes/README.md`](wireframes/README.md)

### 컬러 (Vercel 다크)
- 배경: `#18181b` (페이지) / `#000000` (앱) / `#0a0a0a` (카드)
- 텍스트: `#ffffff` / `#a1a1aa` / `#71717a` / `#d4d4d8`
- 등급: `#00d68f` (우수) / `#f5a524` (보통) / `#71717a` (약함)
- 축 그룹: `#a78bfa` (변화 3축, 라벤더) / `#34d399` (연출 3축, 민트)
- 관점 차이: `rgba(245, 165, 36, 0.04)` 배경 + `#f5a524` 액센트

### 타이포그래피
- 한국어: Pretendard (CDN inline)
- 영문: Inter
- 숫자/코드: JetBrains Mono
- 두 weight만 사용 (400, 500). 600·700 금지.

### 라운드
- 카드 12px, 버튼/입력 6~8px, 뱃지 3~6px, 미니 차트 2~4px

---

## UX 원칙

1. **한국어 우선** — 모든 라벨/버튼/메시지 한국어. URL만 영문 슬러그 (`/analyze`, `/detail`, `/archive`)
2. **AI 가설 시각화** — AI 출력에 "AI 가설" 톤(가능성/추정 표현). 마케터의 최종 결정과 시각적 분리
3. **노드 진행 시각화** — LangGraph 노드 흐름이 사용자에게도 보이도록 실시간 시각화 (페이지 1)
4. **점수보다 근거** — 게이지 점수보다 평가 근거 텍스트가 더 도드라지게 배치
5. **슈퍼센트 톤** — 차분한 다크 + 차분한 블루/네이비 액센트

---

## 상태 관리 패턴 (`session_state`)

| 키 | 용도 | 초기화 |
|---|---|---|
| `pending_match` | 같은 영상 검증 카드 데이터 (분기 밖 렌더용) | 매칭 시 set, 두 버튼 클릭 시 pop |
| `force_reanalyze` | 1회용 sentinel — 강제 재분석 시 검증 우회 | `True` set → 검증 시점 즉시 pop |
| `nav_slug` | 페이지 2 라우팅 백업 채널 (query_params 미전달 케이스) | 페이지 진입 시 query_params 또는 nav_slug 둘 다 시도 |
| `search_query` / `_search_input` | 의미 검색 active 값 / input 임시 값 분리 | `[찾기]`/Enter `on_click`+`on_change`로 commit |
| `pending_delete` / `pending_delete_hard_default` | 삭제 다이얼로그 트리거 | 다이얼로그 닫힘 시 pop |
| `show_deleted` | 삭제된 영상 토글 | `st.toggle` 으로 직접 |

---

## 다음 문서

→ [메인 README로 돌아가기](../README.md)
→ [시각 명세 (HTML 시안 + 디자인 토큰)](wireframes/README.md)
→ [LangSmith 트레이스 자산](langsmith_traces.md)
