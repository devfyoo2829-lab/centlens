"""영상 분석 자산의 데이터 소스 추상화.

Streamlit UI는 ``VideoRepository`` 인터페이스에만 의존한다. 구현체는 두 가지:

- ``JsonRepository``: ``demo_cache/`` 폴더의 JSON을 읽고 쓴다 (오프라인/시연 안정성).
- ``SupabaseRepository``: PostgreSQL + pgvector 백엔드 (시맨틱 검색·누적 자산).

환경변수 ``DATA_SOURCE`` (기본 "json")로 팩토리 ``get_repository()``가 어느 구현을
반환할지 결정한다. SupabaseRepository는 본 단계에서는 stub이며 단계 3에서 구현된다.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from centlens.graph.state import AxisScore

logger = logging.getLogger(__name__)


AXES: tuple[str, ...] = ("movement", "growth", "expansion", "camera", "color", "sound")
EMBED_MODEL: str = "text-embedding-3-small"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CACHE_DIR: Path = _PROJECT_ROOT / "demo_cache"


# ─────────────────────────────────────────────────────────────────────────────
# 데이터 모델
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class AxisTriplet:
    """단일 축의 A·B·final 묶음. demo_cache의 ``axis_scores[ax]`` 형태와 1:1."""

    a: Optional[AxisScore] = None
    b: Optional[AxisScore] = None
    final: Optional[AxisScore] = None

    @classmethod
    def from_dict(cls, d: dict) -> "AxisTriplet":
        return cls(a=d.get("a"), b=d.get("b"), final=d.get("final"))

    def to_dict(self) -> dict:
        return {"a": self.a, "b": self.b, "final": self.final}


@dataclass
class VideoRecord:
    """영상 1편의 분석 자산 — Repository 입출력 단위."""

    slug: str
    game_name: str
    genre: str
    category: str  # 'new' | 'competitor' | 'trend'
    publisher: Optional[str] = None

    axis_scores: dict[str, AxisTriplet] = field(default_factory=dict)
    grade: Optional[str] = None
    weakest_axis: Optional[str] = None
    total_score: Optional[float] = None

    durations_sec: dict[str, Optional[float]] = field(default_factory=dict)
    total_elapsed_sec: Optional[float] = None
    started_at: Optional[str] = None

    errors: list[str] = field(default_factory=list)

    video_path: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None

    embedding: Optional[list[float]] = None
    embedding_dim: Optional[int] = None

    @classmethod
    def from_cache_json(
        cls,
        cache: dict,
        embedding: Optional[list[float]] = None,
    ) -> "VideoRecord":
        """``demo_cache/{slug}.json`` 형식을 ``VideoRecord``로 역직렬화한다."""
        meta = cache.get("metadata") or {}
        ax_raw = cache.get("axis_scores") or {}
        return cls(
            slug=cache["slug"],
            game_name=meta.get("game_name", ""),
            genre=meta.get("genre", ""),
            category=meta.get("category", ""),
            publisher=meta.get("publisher"),
            axis_scores={
                ax: AxisTriplet.from_dict(ax_raw[ax]) for ax in AXES if ax in ax_raw
            },
            grade=cache.get("grade"),
            weakest_axis=cache.get("weakest_axis"),
            total_score=cache.get("total_score"),
            durations_sec=dict(cache.get("durations_sec") or {}),
            total_elapsed_sec=cache.get("total_elapsed_sec"),
            started_at=cache.get("started_at"),
            errors=list(cache.get("errors") or []),
            embedding=list(embedding) if embedding else None,
            embedding_dim=cache.get("embedding_dim"),
        )

    def to_cache_json(self) -> dict:
        """``demo_cache/{slug}.json`` 형식으로 직렬화한다 (embedding 제외)."""
        return {
            "slug": self.slug,
            "metadata": {
                "game_name": self.game_name,
                "genre": self.genre,
                "category": self.category,
                "publisher": self.publisher,
            },
            "axis_scores": {ax: t.to_dict() for ax, t in self.axis_scores.items()},
            "grade": self.grade,
            "weakest_axis": self.weakest_axis,
            "total_score": self.total_score,
            "durations_sec": self.durations_sec,
            "total_elapsed_sec": self.total_elapsed_sec,
            "started_at": self.started_at,
            "errors": self.errors,
            "embedding_dim": self.embedding_dim,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 인터페이스
# ─────────────────────────────────────────────────────────────────────────────
@runtime_checkable
class VideoRepository(Protocol):
    """영상 자산 저장소 추상 인터페이스."""

    def list_videos(
        self,
        *,
        category: Optional[str] = None,
        with_embedding: bool = False,
    ) -> list[VideoRecord]: ...

    def get_video(
        self,
        slug: str,
        *,
        with_embedding: bool = False,
    ) -> Optional[VideoRecord]: ...

    def save_video(self, record: VideoRecord) -> None: ...

    def search_semantic(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[tuple[VideoRecord, float]]: ...

    def search_by_vector(
        self,
        vector: list[float],
        top_k: int = 5,
    ) -> list[tuple[VideoRecord, float]]: ...


# ─────────────────────────────────────────────────────────────────────────────
# JSON 구현 — demo_cache/ 폴더 직접 입출력
# ─────────────────────────────────────────────────────────────────────────────
class JsonRepository:
    """demo_cache/*.json 을 읽고 쓰는 파일 시스템 기반 저장소.

    영상 본문은 ``{slug}.json``, 임베딩(1536 float)은 크기가 크므로
    ``{slug}_embedding.json``에 분리 저장한다. ``with_embedding`` 플래그로
    임베딩 로드 비용을 제어한다.
    """

    def __init__(self, cache_dir: Optional[Path | str] = None) -> None:
        self.cache_dir: Path = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR

    def _list_cache_paths(self) -> list[Path]:
        if not self.cache_dir.is_dir():
            return []
        return sorted(
            p for p in self.cache_dir.glob("*.json")
            if not p.name.endswith("_embedding.json")
        )

    def _load_embedding(self, slug: str) -> Optional[list[float]]:
        emb_path = self.cache_dir / f"{slug}_embedding.json"
        if not emb_path.is_file():
            return None
        try:
            data = json.loads(emb_path.read_text(encoding="utf-8"))
            vec = data.get("embedding")
            return list(vec) if vec else None
        except Exception as e:
            logger.warning("JsonRepository: %s 임베딩 로드 실패: %s", slug, e)
            return None

    def list_videos(
        self,
        *,
        category: Optional[str] = None,
        with_embedding: bool = False,
    ) -> list[VideoRecord]:
        records: list[VideoRecord] = []
        for path in self._list_cache_paths():
            try:
                cache = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("JsonRepository: %s 로드 실패: %s", path, e)
                continue
            embedding = self._load_embedding(cache["slug"]) if with_embedding else None
            rec = VideoRecord.from_cache_json(cache, embedding=embedding)
            if category is not None and rec.category != category:
                continue
            records.append(rec)
        return records

    def get_video(
        self,
        slug: str,
        *,
        with_embedding: bool = False,
    ) -> Optional[VideoRecord]:
        path = self.cache_dir / f"{slug}.json"
        if not path.is_file():
            return None
        try:
            cache = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("JsonRepository: %s 로드 실패: %s", path, e)
            return None
        embedding = self._load_embedding(slug) if with_embedding else None
        return VideoRecord.from_cache_json(cache, embedding=embedding)

    def save_video(self, record: VideoRecord) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self.cache_dir / f"{record.slug}.json"
        cache_path.write_text(
            json.dumps(record.to_cache_json(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if record.embedding:
            emb_path = self.cache_dir / f"{record.slug}_embedding.json"
            emb_path.write_text(
                json.dumps({"slug": record.slug, "embedding": record.embedding}),
                encoding="utf-8",
            )

    def search_semantic(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[tuple[VideoRecord, float]]:
        """텍스트 쿼리를 OpenAI text-embedding-3-small로 임베딩 후 벡터 검색."""
        from openai import OpenAI

        client = OpenAI()
        resp = client.embeddings.create(model=EMBED_MODEL, input=query)
        vec = list(resp.data[0].embedding)
        return self.search_by_vector(vec, top_k=top_k)

    def search_by_vector(
        self,
        vector: list[float],
        top_k: int = 5,
    ) -> list[tuple[VideoRecord, float]]:
        """1536차원 벡터와 코사인 유사도로 top_k 영상 반환."""
        import numpy as np

        records = [r for r in self.list_videos(with_embedding=True) if r.embedding]
        if not records:
            return []

        q = np.asarray(vector, dtype=np.float32)
        q_norm_factor = float(np.linalg.norm(q)) + 1e-12
        q_unit = q / q_norm_factor

        results: list[tuple[VideoRecord, float]] = []
        for r in records:
            v = np.asarray(r.embedding, dtype=np.float32)
            v_unit = v / (float(np.linalg.norm(v)) + 1e-12)
            sim = float(np.dot(q_unit, v_unit))
            results.append((r, sim))

        results.sort(key=lambda t: t[1], reverse=True)
        return results[:top_k]


# ─────────────────────────────────────────────────────────────────────────────
# Supabase 구현 — 단계 3에서 채워질 stub
# ─────────────────────────────────────────────────────────────────────────────
class SupabaseRepository:
    """Supabase + pgvector 백엔드 stub. 모든 메서드는 단계 3에서 구현된다."""

    def __init__(self) -> None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SupabaseRepository: SUPABASE_URL/SUPABASE_KEY 가 .env에 설정되어 있지 않음"
            )
        self._url = url
        self._key = key

    def list_videos(
        self,
        *,
        category: Optional[str] = None,
        with_embedding: bool = False,
    ) -> list[VideoRecord]:
        raise NotImplementedError("SupabaseRepository.list_videos: 단계 3에서 구현 예정")

    def get_video(
        self,
        slug: str,
        *,
        with_embedding: bool = False,
    ) -> Optional[VideoRecord]:
        raise NotImplementedError("SupabaseRepository.get_video: 단계 3에서 구현 예정")

    def save_video(self, record: VideoRecord) -> None:
        raise NotImplementedError("SupabaseRepository.save_video: 단계 3에서 구현 예정")

    def search_semantic(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[tuple[VideoRecord, float]]:
        raise NotImplementedError("SupabaseRepository.search_semantic: 단계 3에서 구현 예정")

    def search_by_vector(
        self,
        vector: list[float],
        top_k: int = 5,
    ) -> list[tuple[VideoRecord, float]]:
        raise NotImplementedError("SupabaseRepository.search_by_vector: 단계 3에서 구현 예정")


# ─────────────────────────────────────────────────────────────────────────────
# 팩토리
# ─────────────────────────────────────────────────────────────────────────────
def get_repository() -> VideoRepository:
    """환경변수 ``DATA_SOURCE`` (기본 "json")에 따라 구현체를 반환한다."""
    data_source = (os.getenv("DATA_SOURCE") or "json").lower()
    if data_source == "json":
        return JsonRepository()
    if data_source == "supabase":
        return SupabaseRepository()
    raise ValueError(
        f"DATA_SOURCE={data_source!r} 미지원 — 'json' 또는 'supabase'만 허용"
    )
