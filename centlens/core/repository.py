"""영상 분석 자산의 데이터 소스 추상화.

Streamlit UI는 ``VideoRepository`` 인터페이스에만 의존한다. 구현체는 두 가지:

- ``JsonRepository``: ``demo_cache/`` 폴더의 JSON을 읽고 쓴다 (오프라인/시연 안정성).
- ``SupabaseRepository``: PostgreSQL + pgvector 백엔드 (시맨틱 검색·누적 자산).

환경변수 ``DATA_SOURCE`` (기본 "json")로 팩토리 ``get_repository()``가 어느 구현을
반환할지 결정한다. SupabaseRepository는 본 단계에서는 stub이며 단계 3에서 구현된다.
"""

import hashlib
import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from centlens.graph.state import AxisScore

logger = logging.getLogger(__name__)


AXES: tuple[str, ...] = ("movement", "growth", "expansion", "camera", "color", "sound")
EMBED_MODEL: str = "text-embedding-3-small"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CACHE_DIR: Path = _PROJECT_ROOT / "demo_cache"

# 시드 5편 — 슈퍼센트 공식 영상. 사용자가 명시적으로 삭제하지 않았다면 페이지 진입 시
# 자동 복원되도록 보호한다. ``data/.deleted_seeds`` 에 한 줄로 기록되면 복원 대상에서 제외.
SEED_SLUGS: tuple[str, ...] = (
    "burger_please_drive_thru",
    "pizza_ready_break",
    "snake_clash_morph",
    "twerk_race_gate",
    "kingshot_expansion",
)

_DELETED_SEEDS_LOG: Path = _PROJECT_ROOT / "data" / ".deleted_seeds"


def sha256_file(path: Path | str) -> str:
    """파일을 64KB 청크로 읽어 SHA-256 16진수 문자열 반환."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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

    # 정확 매칭용 SHA-256 — 같은 mp4를 다시 업로드했을 때 즉시 동일 영상 식별.
    file_hash: Optional[str] = None

    # Soft delete — None 이면 활성, ISO timestamp 가 들어있으면 휴지통(.trash) 보관 상태.
    deleted_at: Optional[str] = None

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
            file_hash=cache.get("file_hash"),
            deleted_at=cache.get("deleted_at"),
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
            "file_hash": self.file_hash,
            "deleted_at": self.deleted_at,
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
        include_deleted: bool = False,
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

    def delete_video(self, slug: str, *, hard: bool = False) -> bool: ...

    def restore_video(self, slug: str) -> bool: ...

    def restore_missing_seeds(self) -> list[str]: ...

    def find_by_hash(self, file_hash: str) -> Optional[VideoRecord]: ...

    def find_similar_video(
        self,
        query_embedding: list[float],
        threshold: float = 0.95,
    ) -> Optional[tuple[VideoRecord, float]]: ...


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
        include_deleted: bool = False,
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
            if not include_deleted and rec.deleted_at is not None:
                continue
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

    # ── 삭제 + 복원 ──────────────────────────────────────────────────────────
    def delete_video(self, slug: str, *, hard: bool = False) -> bool:
        """기본은 soft delete: ``deleted_at`` 기록 + 자산을 ``data/.trash/{slug}/`` 로 이동.

        ``hard=True`` 면 즉시 영구 삭제 (cache JSON + 모든 자산 unlink) 후 시드면
        ``.deleted_seeds`` 에 등재해 자동 복원 우회.

        Returns:
            상태 변경이 일어나면 True.
        """
        if hard:
            return self._hard_delete(slug)
        return self._soft_delete(slug)

    def _soft_delete(self, slug: str) -> bool:
        rec = self.get_video(slug, with_embedding=True)
        if rec is None or rec.deleted_at is not None:
            return False
        rec.deleted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.save_video(rec)

        trash_dir = _PROJECT_ROOT / "data" / ".trash" / slug
        trash_dir.mkdir(parents=True, exist_ok=True)

        for asset in (
            _PROJECT_ROOT / "data" / "videos" / f"{slug}.mp4",
            _PROJECT_ROOT / "data" / "scripts" / f"{slug}.txt",
        ):
            if asset.is_file():
                try:
                    shutil.move(str(asset), str(trash_dir / asset.name))
                except Exception as e:
                    logger.warning("_soft_delete[%s]: move %s 실패: %s", slug, asset, e)

        frames_dir = _PROJECT_ROOT / "data" / "frames" / slug
        if frames_dir.is_dir():
            try:
                shutil.move(str(frames_dir), str(trash_dir / "frames"))
            except Exception as e:
                logger.warning("_soft_delete[%s]: frames move 실패: %s", slug, e)

        logger.info("_soft_delete[%s]: deleted_at=%s, 자산 → %s", slug, rec.deleted_at, trash_dir)
        return True

    def _hard_delete(self, slug: str) -> bool:
        deleted_any = False

        # .trash 안에 자산이 이미 있다면 그것도 정리
        trash_dir = _PROJECT_ROOT / "data" / ".trash" / slug
        if trash_dir.is_dir():
            try:
                shutil.rmtree(trash_dir)
                deleted_any = True
            except Exception as e:
                logger.warning("_hard_delete[%s]: trash rmtree 실패: %s", slug, e)

        candidates: list[Path] = [
            self.cache_dir / f"{slug}.json",
            self.cache_dir / f"{slug}_embedding.json",
            _PROJECT_ROOT / "data" / "videos" / f"{slug}.mp4",
            _PROJECT_ROOT / "data" / "scripts" / f"{slug}.txt",
        ]
        for p in candidates:
            if p.is_file():
                try:
                    p.unlink()
                    deleted_any = True
                except Exception as e:
                    logger.warning("_hard_delete[%s]: %s 실패: %s", slug, p, e)

        frames_dir = _PROJECT_ROOT / "data" / "frames" / slug
        if frames_dir.is_dir():
            try:
                shutil.rmtree(frames_dir)
                deleted_any = True
            except Exception as e:
                logger.warning("_hard_delete[%s]: frames rmtree 실패: %s", slug, e)

        # 시드면 자동 복원 우회 등재 (hard 일 때만)
        if slug in SEED_SLUGS:
            self._mark_seed_deleted(slug)

        return deleted_any

    def restore_video(self, slug: str) -> bool:
        """soft-deleted 영상을 활성으로 되돌림 — ``deleted_at=None`` + ``.trash/`` 자산 복귀."""
        rec = self.get_video(slug, with_embedding=True)
        if rec is None or rec.deleted_at is None:
            return False

        rec.deleted_at = None
        self.save_video(rec)

        trash_dir = _PROJECT_ROOT / "data" / ".trash" / slug
        if trash_dir.is_dir():
            for item in list(trash_dir.iterdir()):
                try:
                    if item.name == "frames":
                        target = _PROJECT_ROOT / "data" / "frames" / slug
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists():
                            shutil.move(str(item), str(target))
                    elif item.suffix == ".mp4":
                        target = _PROJECT_ROOT / "data" / "videos" / item.name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists():
                            shutil.move(str(item), str(target))
                    elif item.suffix == ".txt":
                        target = _PROJECT_ROOT / "data" / "scripts" / item.name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists():
                            shutil.move(str(item), str(target))
                except Exception as e:
                    logger.warning("restore_video[%s]: %s 복귀 실패: %s", slug, item, e)
            try:
                trash_dir.rmdir()
            except OSError:
                pass

        logger.info("restore_video[%s]: 복원 완료", slug)
        return True

    def _mark_seed_deleted(self, slug: str) -> None:
        _DELETED_SEEDS_LOG.parent.mkdir(parents=True, exist_ok=True)
        existing = self._read_deleted_seeds()
        if slug in existing:
            return
        existing.add(slug)
        _DELETED_SEEDS_LOG.write_text(
            "\n".join(sorted(existing)) + "\n", encoding="utf-8"
        )

    @staticmethod
    def _read_deleted_seeds() -> set[str]:
        if not _DELETED_SEEDS_LOG.is_file():
            return set()
        try:
            return {
                line.strip()
                for line in _DELETED_SEEDS_LOG.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }
        except Exception:
            return set()

    def clear_deleted_seeds_log(self) -> None:
        """delete_log 비움 — 다음 ``restore_missing_seeds()`` 가 모든 시드 복원."""
        if _DELETED_SEEDS_LOG.is_file():
            _DELETED_SEEDS_LOG.unlink()

    def restore_missing_seeds(self) -> list[str]:
        """``demo_cache/seed/`` 의 시드 자산 중 라이브에서 누락된 것을 복원.

        ``data/.deleted_seeds`` 에 등재된 slug는 건너뛴다 (사용자가 의도적으로 삭제).
        Returns:
            새로 복원된 slug 리스트.
        """
        deleted = self._read_deleted_seeds()
        seed_cache_dir = self.cache_dir / "seed"
        seed_videos_dir = _PROJECT_ROOT / "data" / "seed_videos"
        seed_frames_dir = _PROJECT_ROOT / "data" / "seed_frames"
        seed_scripts_dir = _PROJECT_ROOT / "data" / "seed_scripts"

        restored: list[str] = []
        for slug in SEED_SLUGS:
            if slug in deleted:
                continue
            live_cache = self.cache_dir / f"{slug}.json"
            if live_cache.is_file():
                continue  # 이미 있음

            seed_cache = seed_cache_dir / f"{slug}.json"
            if not seed_cache.is_file():
                logger.warning("restore_missing_seeds[%s]: 백업 없음 %s", slug, seed_cache)
                continue

            # cache + embedding
            try:
                shutil.copy2(seed_cache, live_cache)
                seed_emb = seed_cache_dir / f"{slug}_embedding.json"
                if seed_emb.is_file():
                    shutil.copy2(seed_emb, self.cache_dir / f"{slug}_embedding.json")
            except Exception as e:
                logger.warning("restore_missing_seeds[%s]: cache 복사 실패 %s", slug, e)
                continue

            # video / frames / script
            seed_mp4 = seed_videos_dir / f"{slug}.mp4"
            live_mp4 = _PROJECT_ROOT / "data" / "videos" / f"{slug}.mp4"
            if seed_mp4.is_file() and not live_mp4.is_file():
                live_mp4.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(seed_mp4, live_mp4)

            seed_frames = seed_frames_dir / slug
            live_frames = _PROJECT_ROOT / "data" / "frames" / slug
            if seed_frames.is_dir() and not live_frames.is_dir():
                shutil.copytree(seed_frames, live_frames)

            seed_script = seed_scripts_dir / f"{slug}.txt"
            live_script = _PROJECT_ROOT / "data" / "scripts" / f"{slug}.txt"
            if seed_script.is_file() and not live_script.is_file():
                live_script.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(seed_script, live_script)

            logger.info("restore_missing_seeds[%s]: 복원 완료", slug)
            restored.append(slug)
        return restored

    # ── 매칭 ────────────────────────────────────────────────────────────────
    def find_by_hash(self, file_hash: str) -> Optional[VideoRecord]:
        """``file_hash`` 가 정확히 일치하는 영상 1편 반환. 없으면 None."""
        if not file_hash:
            return None
        for path in self._list_cache_paths():
            try:
                cache = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if cache.get("file_hash") == file_hash:
                return VideoRecord.from_cache_json(cache)
        return None

    def find_similar_video(
        self,
        query_embedding: list[float],
        threshold: float = 0.95,
    ) -> Optional[tuple[VideoRecord, float]]:
        """기존 영상 중 임베딩 코사인 유사도가 ``threshold`` 이상인 top1 반환."""
        results = self.search_by_vector(list(query_embedding), top_k=1)
        if not results:
            return None
        rec, sim = results[0]
        if sim >= threshold:
            return (rec, sim)
        return None


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
        include_deleted: bool = False,
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

    def delete_video(self, slug: str, *, hard: bool = False) -> bool:
        raise NotImplementedError("SupabaseRepository.delete_video: 단계 3에서 구현 예정")

    def restore_video(self, slug: str) -> bool:
        raise NotImplementedError("SupabaseRepository.restore_video: 단계 3에서 구현 예정")

    def restore_missing_seeds(self) -> list[str]:
        raise NotImplementedError("SupabaseRepository.restore_missing_seeds: 단계 3에서 구현 예정")

    def find_by_hash(self, file_hash: str) -> Optional[VideoRecord]:
        raise NotImplementedError("SupabaseRepository.find_by_hash: 단계 3에서 구현 예정")

    def find_similar_video(
        self,
        query_embedding: list[float],
        threshold: float = 0.95,
    ) -> Optional[tuple[VideoRecord, float]]:
        raise NotImplementedError("SupabaseRepository.find_similar_video: 단계 3에서 구현 예정")


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
