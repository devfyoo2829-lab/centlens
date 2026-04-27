-- =====================================================
-- CentLens 데이터베이스 스키마
-- =====================================================
-- 슈퍼센트 자체 6축 평가 프레임 기반 광고 영상 분석 데이터
-- 실행: Supabase Dashboard → SQL Editor → New Query → 붙여넣고 Run
-- =====================================================

-- pgvector 확장 활성화 (시맨틱 검색용)
create extension if not exists vector;

-- =====================================================
-- 1. videos 테이블 — 영상 메타데이터 + 임베딩
-- =====================================================
create table if not exists videos (
  id uuid primary key default gen_random_uuid(),
  category text check (category in ('new', 'competitor', 'trend')),
  game_name text not null,
  genre text not null,
  uploaded_at timestamptz default now(),
  video_path text,
  script text,
  embedding vector(1536)
);

create index if not exists idx_videos_category on videos(category);
create index if not exists idx_videos_game_name on videos(game_name);
create index if not exists idx_videos_uploaded_at on videos(uploaded_at desc);

-- =====================================================
-- 2. axis_scores 테이블 — 6축 점수 + 근거 (A/B 교차)
-- =====================================================
create table if not exists axis_scores (
  id uuid primary key default gen_random_uuid(),
  video_id uuid references videos(id) on delete cascade,
  axis text check (axis in ('movement','growth','expansion','camera','color','sound')),
  score_a numeric check (score_a >= 1 and score_a <= 5),
  score_b numeric check (score_b >= 1 and score_b <= 5),
  score_final numeric check (score_final >= 1 and score_final <= 5),
  rationale text,
  confidence numeric check (confidence >= 0 and confidence <= 1)
);

create index if not exists idx_axis_scores_video_id on axis_scores(video_id);
create index if not exists idx_axis_scores_axis on axis_scores(axis);

-- =====================================================
-- 3. grades 테이블 — weakest-link 종합 등급
-- =====================================================
create table if not exists grades (
  id uuid primary key default gen_random_uuid(),
  video_id uuid references videos(id) on delete cascade,
  grade text check (grade in ('strong','medium','weak')),
  weakest_axis text,
  total_score numeric
);

create index if not exists idx_grades_video_id on grades(video_id);
create index if not exists idx_grades_grade on grades(grade);

-- =====================================================
-- 4. marketer_comments 테이블 — 마케터 코멘트 + 결정
-- =====================================================
create table if not exists marketer_comments (
  id uuid primary key default gen_random_uuid(),
  video_id uuid references videos(id) on delete cascade,
  comment text,
  override_reason text,
  created_at timestamptz default now()
);

create index if not exists idx_marketer_comments_video_id on marketer_comments(video_id);

-- =====================================================
-- 5. node_traces 테이블 — LangGraph 노드 실행 흔적
-- =====================================================
create table if not exists node_traces (
  id uuid primary key default gen_random_uuid(),
  video_id uuid references videos(id) on delete cascade,
  node_name text,
  duration_ms integer,
  input_tokens integer,
  output_tokens integer,
  status text check (status in ('success','error','skipped')),
  error_message text,
  executed_at timestamptz default now()
);

create index if not exists idx_node_traces_video_id on node_traces(video_id);
create index if not exists idx_node_traces_executed_at on node_traces(executed_at desc);

-- =====================================================
-- 시맨틱 검색용 인덱스 (HNSW)
-- =====================================================
create index if not exists idx_videos_embedding on videos
  using hnsw (embedding vector_cosine_ops);

-- =====================================================
-- Row Level Security (RLS) 활성화 + 정책
-- =====================================================
-- 데모 단계: anon 키로 모든 테이블 read/write 허용
-- 프로덕션에서는 마케터 인증 + 역할별 정책으로 교체 예정

alter table videos enable row level security;
alter table axis_scores enable row level security;
alter table grades enable row level security;
alter table marketer_comments enable row level security;
alter table node_traces enable row level security;

-- 데모용: 모든 anon 사용자에게 read/write 허용
create policy "demo_videos_all" on videos for all using (true) with check (true);
create policy "demo_axis_scores_all" on axis_scores for all using (true) with check (true);
create policy "demo_grades_all" on grades for all using (true) with check (true);
create policy "demo_comments_all" on marketer_comments for all using (true) with check (true);
create policy "demo_traces_all" on node_traces for all using (true) with check (true);
-- =====================================================
-- 검증: 생성된 테이블 확인
-- =====================================================
select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in ('videos', 'axis_scores', 'grades', 'marketer_comments', 'node_traces')
order by table_name;