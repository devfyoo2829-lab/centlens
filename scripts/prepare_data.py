"""
영상 데이터 준비 스크립트.

Annie 글이 분석한 5개 게임의 슈퍼센트 공식 광고 영상을 다운로드하고,
프레임 5장을 추출한 뒤 Whisper API로 STT를 수행하여 data/ 폴더에 저장한다.

사용법:
    python scripts/prepare_data.py

사전 요구사항:
    - yt-dlp 설치: pip install yt-dlp
    - ffmpeg 설치 (시스템 패키지)
    - .env 파일에 OPENAI_API_KEY 설정

출력 구조:
    data/
    ├── videos/{slug}.mp4        다운로드된 영상
    ├── frames/{slug}/0.jpg      0% 시점 프레임
    ├── frames/{slug}/1.jpg      5% 시점 프레임
    ├── frames/{slug}/2.jpg      25% 시점 프레임
    ├── frames/{slug}/3.jpg      50% 시점 프레임
    ├── frames/{slug}/4.jpg      95% 시점 프레임
    └── scripts/{slug}.txt       Whisper STT 결과
"""

import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Annie 글이 분석한 5개 게임의 공식 슈퍼센트 광고 영상 URL
# 실제 URL은 슈퍼센트 공식 YouTube 채널 또는 Pizza Ready 등의 게임 채널에서 확인 후 채워넣기

TARGET_VIDEOS = [
    # 슈퍼센트 자사 게임 (분류: 신규)
    {
        "slug": "burger_please_drive_thru",
        "game_name": "Burger Please",
        "genre": "하이퍼캐주얼",
        "category": "new",
        "publisher": "Supercent",
        "youtube_url": "https://www.youtube.com/watch?v=z6uoNzTQqsI",
        "description": "Annie 글에서 절단 움직임 + 대량 오브젝트 사례로 인용",
    },
    {
        "slug": "pizza_ready_break",
        "game_name": "Pizza Ready",
        "genre": "하이퍼캐주얼",
        "category": "new",
        "publisher": "Supercent",
        "youtube_url": "https://www.youtube.com/watch?v=2sXUK_X97jc",
        "description": "Annie 글에서 유리병 굴리기 + 파편 사례로 인용",
    },
    {
        "slug": "snake_clash_morph",
        "game_name": "Snake Clash",
        "genre": "하이브리드캐주얼",
        "category": "new",
        "publisher": "Supercent",
        "youtube_url": "https://www.youtube.com/watch?v=CA0Iw_q-r_g",
        "description": "Annie 글에서 시작 3초 만에 외형 변화 사례로 인용",
    },
    # 경쟁사·시장 트렌드 게임 (Annie 글이 시장 사례로 분석)
    {
        "slug": "twerk_race_gate",
        "game_name": "Twerk Race 3D",
        "genre": "하이퍼캐주얼",
        "category": "competitor",
        "publisher": "Freeplay LLC",
        "youtube_url": "https://www.youtube.com/watch?v=FZ5HF8erSXI",
        "description": "Annie 글에서 게이트 통과 신체 변화 사례로 인용 (외부 시장 사례)",
    },
    {
        "slug": "kingshot_expansion",
        "game_name": "Kingshot",
        "genre": "전략",
        "category": "competitor",
        "publisher": "Century Games",
        "youtube_url": "https://www.facebook.com/61560003321785/videos/1944219636114772",
        "description": "Annie 글에서 자원 → 타워 확장 사례로 인용 (외부 시장 사례)",
    },
]

DATA_DIR = Path("data")
VIDEOS_DIR = DATA_DIR / "videos"
FRAMES_DIR = DATA_DIR / "frames"
SCRIPTS_DIR = DATA_DIR / "scripts"


def setup_directories() -> None:
    """데이터 디렉토리 생성."""
    for d in [VIDEOS_DIR, FRAMES_DIR, SCRIPTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def download_video(url: str, output_path: Path) -> bool:
    """yt-dlp로 YouTube 영상 다운로드.

    Args:
        url: YouTube URL
        output_path: 저장 경로

    Returns:
        다운로드 성공 여부
    """
    if output_path.exists():
        print(f"  [skip] 이미 존재: {output_path}")
        return True

    if "PLACEHOLDER" in url:
        print(f"  [warn] URL이 PLACEHOLDER 상태입니다. 실제 URL로 교체 필요: {output_path.stem}")
        return False

    try:
        cmd = [
            "yt-dlp",
            "-f", "best[ext=mp4][height<=720]/best[ext=mp4]/best",
            "-o", str(output_path),
            url,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"  [done] 다운로드 완료: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [error] 다운로드 실패: {e.stderr.decode()}")
        return False


def get_video_duration(video_path: Path) -> float:
    """영상 길이(초) 측정.

    Args:
        video_path: 영상 파일 경로

    Returns:
        영상 길이(초)
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def extract_frames(video_path: Path, output_dir: Path) -> bool:
    """영상에서 5개 프레임 추출.

    추출 시점: 0% / 5% / 25% / 50% / 95%

    Args:
        video_path: 영상 파일 경로
        output_dir: 프레임 저장 디렉토리

    Returns:
        추출 성공 여부
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if all((output_dir / f"{i}.jpg").exists() for i in range(5)):
        print(f"  [skip] 프레임 이미 존재: {output_dir}")
        return True

    try:
        duration = get_video_duration(video_path)
        timestamps = [
            0,
            duration * 0.05,
            duration * 0.25,
            duration * 0.50,
            duration * 0.95,
        ]

        for i, ts in enumerate(timestamps):
            output_file = output_dir / f"{i}.jpg"
            cmd = [
                "ffmpeg",
                "-y",
                "-ss", str(ts),
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "2",
                str(output_file),
            ]
            subprocess.run(cmd, check=True, capture_output=True)

        print(f"  [done] 프레임 5장 추출: {output_dir}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [error] 프레임 추출 실패: {e.stderr.decode()}")
        return False


def transcribe_audio(video_path: Path, output_path: Path, client: OpenAI) -> bool:
    """Whisper API로 영상 나레이션 추출.

    Args:
        video_path: 영상 파일 경로
        output_path: STT 결과 저장 경로
        client: OpenAI 클라이언트

    Returns:
        STT 성공 여부
    """
    if output_path.exists():
        print(f"  [skip] STT 이미 존재: {output_path}")
        return True

    try:
        with open(video_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="text",
            )
        output_path.write_text(transcript, encoding="utf-8")
        print(f"  [done] STT 완료: {output_path}")
        return True
    except Exception as e:
        print(f"  [error] STT 실패: {e}")
        return False


def main() -> None:
    """메인 실행 함수."""
    print("=" * 60)
    print("CentLens 데이터 준비 스크립트")
    print("=" * 60)

    setup_directories()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n[error] OPENAI_API_KEY가 .env에 설정되지 않았습니다.")
        print("        Whisper STT를 건너뜁니다.")
        client = None
    else:
        client = OpenAI(api_key=api_key)

    summary = []

    for video in TARGET_VIDEOS:
        slug = video["slug"]
        print(f"\n[{slug}] {video['game_name']}")
        print(f"  설명: {video['description']}")

        video_path = VIDEOS_DIR / f"{slug}.mp4"
        frames_dir = FRAMES_DIR / slug
        script_path = SCRIPTS_DIR / f"{slug}.txt"

        # 1. 영상 다운로드
        downloaded = download_video(video["youtube_url"], video_path)

        # 2. 프레임 추출 (영상이 있을 때만)
        if downloaded and video_path.exists():
            extract_frames(video_path, frames_dir)

        # 3. STT (영상이 있고 OpenAI 키가 있을 때만)
        if downloaded and video_path.exists() and client:
            transcribe_audio(video_path, script_path, client)

        summary.append({
            "slug": slug,
            "game_name": video["game_name"],
            "genre": video["genre"],
            "video_exists": video_path.exists(),
            "frames_count": len(list(frames_dir.glob("*.jpg"))) if frames_dir.exists() else 0,
            "script_exists": script_path.exists(),
        })

    # 요약 출력
    print("\n" + "=" * 60)
    print("준비 완료 요약")
    print("=" * 60)
    for s in summary:
        print(f"  {s['slug']}")
        print(f"    영상: {'O' if s['video_exists'] else 'X'} | "
              f"프레임: {s['frames_count']}/5 | "
              f"STT: {'O' if s['script_exists'] else 'X'}")

    # 메타데이터 저장
    metadata_path = DATA_DIR / "metadata.json"
    metadata_path.write_text(
        json.dumps(TARGET_VIDEOS, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n메타데이터 저장: {metadata_path}")


if __name__ == "__main__":
    main()
