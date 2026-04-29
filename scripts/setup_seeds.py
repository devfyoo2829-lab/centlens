"""시드 5편(슈퍼센트 공식 영상)을 백업 폴더로 복제하고 file_hash 메타데이터를 추가한다.

일회성 setup 스크립트. 실행 후:
- ``data/seed_videos/{slug}.mp4`` — 시드 영상 원본
- ``data/seed_frames/{slug}/{0..4}.jpg`` — 시드 프레임 5장
- ``data/seed_scripts/{slug}.txt`` — 시드 STT 스크립트
- ``demo_cache/seed/{slug}.json`` + ``{slug}_embedding.json`` — 시드 분석 결과
- 라이브 ``demo_cache/{slug}.json`` 에도 ``file_hash`` 필드 추가 (시드 5 + 잔존 사용자 1)

사용법:
    python scripts/setup_seeds.py
"""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_SLUGS = (
    "burger_please_drive_thru",
    "pizza_ready_break",
    "snake_clash_morph",
    "twerk_race_gate",
    "kingshot_expansion",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_if_missing(src: Path, dst: Path) -> bool:
    if dst.is_file() or dst.is_dir():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return True


def add_file_hash_to_cache(cache_path: Path, file_hash: str) -> bool:
    """demo_cache JSON에 file_hash 필드를 추가/갱신."""
    if not cache_path.is_file():
        return False
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    if data.get("file_hash") == file_hash:
        return False
    data["file_hash"] = file_hash
    cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def main() -> None:
    print("=" * 60)
    print("CentLens 시드 백업 + file_hash 메타 추가")
    print("=" * 60)

    seed_videos_dir = ROOT / "data" / "seed_videos"
    seed_frames_dir = ROOT / "data" / "seed_frames"
    seed_scripts_dir = ROOT / "data" / "seed_scripts"
    seed_cache_dir = ROOT / "demo_cache" / "seed"
    for d in (seed_videos_dir, seed_frames_dir, seed_scripts_dir, seed_cache_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 1) 시드 5편 백업 + file_hash 부여
    for slug in SEED_SLUGS:
        print(f"\n[{slug}]")
        live_mp4 = ROOT / "data" / "videos" / f"{slug}.mp4"
        live_frames = ROOT / "data" / "frames" / slug
        live_script = ROOT / "data" / "scripts" / f"{slug}.txt"
        live_cache = ROOT / "demo_cache" / f"{slug}.json"
        live_emb = ROOT / "demo_cache" / f"{slug}_embedding.json"

        if not live_mp4.is_file():
            print(f"  [skip] 영상 없음: {live_mp4}")
            continue

        # 백업 복사
        copied = copy_if_missing(live_mp4, seed_videos_dir / f"{slug}.mp4")
        print(f"  seed_videos: {'복사' if copied else 'skip'}")
        copied = copy_if_missing(live_frames, seed_frames_dir / slug) if live_frames.is_dir() else False
        print(f"  seed_frames: {'복사' if copied else 'skip'}")
        if live_script.is_file():
            copied = copy_if_missing(live_script, seed_scripts_dir / f"{slug}.txt")
            print(f"  seed_scripts: {'복사' if copied else 'skip'}")
        copied = copy_if_missing(live_cache, seed_cache_dir / f"{slug}.json")
        print(f"  seed_cache: {'복사' if copied else 'skip'}")
        if live_emb.is_file():
            copied = copy_if_missing(live_emb, seed_cache_dir / f"{slug}_embedding.json")
            print(f"  seed_emb: {'복사' if copied else 'skip'}")

        # file_hash 계산
        h = sha256_file(live_mp4)
        print(f"  sha256: {h[:20]}...")

        # 라이브 + seed cache JSON 양쪽에 기록
        live_added = add_file_hash_to_cache(live_cache, h)
        seed_added = add_file_hash_to_cache(seed_cache_dir / f"{slug}.json", h)
        print(f"  file_hash 라이브: {'추가' if live_added else '이미 있음'}, "
              f"seed: {'추가' if seed_added else '이미 있음'}")

    # 2) 잔존 사용자 영상에도 file_hash 부여 (있다면)
    print("\n[non-seed entries]")
    for cache_path in (ROOT / "demo_cache").glob("*.json"):
        if cache_path.name.endswith("_embedding.json"):
            continue
        slug = cache_path.stem
        if slug in SEED_SLUGS:
            continue
        live_mp4 = ROOT / "data" / "videos" / f"{slug}.mp4"
        if not live_mp4.is_file():
            print(f"  [skip] {slug}: mp4 없음")
            continue
        h = sha256_file(live_mp4)
        added = add_file_hash_to_cache(cache_path, h)
        print(f"  {slug}: file_hash {'추가' if added else '이미 있음'} ({h[:12]}...)")

    print("\n완료.")


if __name__ == "__main__":
    main()
