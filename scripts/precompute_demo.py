"""
데모 캐시 사전 생성 스크립트.

prepare_data.py로 준비된 5편 영상에 대해 LangGraph 전체 흐름을 실행하고,
결과를 demo_cache/{slug}.json에 저장한다.

데모 시연 시 영상 멀티모달 처리(1편당 5~10초)를 기다리지 않고
즉시 캐시된 결과를 보여줄 수 있다.

사용법:
    python scripts/precompute_demo.py

사전 요구사항:
    - python scripts/prepare_data.py 실행 완료
    - .env 파일에 ANTHROPIC_API_KEY, OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY 설정
"""

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

# 실제 구현 시 LangGraph 빌더 import
# from centlens.graph.builder import build_centlens_graph

load_dotenv()

DATA_DIR = Path("data")
DEMO_CACHE_DIR = Path("demo_cache")


async def precompute_video(slug: str, metadata: dict) -> dict:
    """단일 영상에 대해 LangGraph 전체 흐름 실행.

    Args:
        slug: 영상 슬러그 (예: "pizza_ready_break")
        metadata: 영상 메타데이터

    Returns:
        LangGraph 실행 결과 (6축 점수 + 등급 + 임베딩)
    """
    print(f"\n[{slug}] 처리 시작")

    # TODO: 실제 구현 시 아래 주석 해제
    # graph = build_centlens_graph()
    # initial_state = {
    #     "video_path": str(DATA_DIR / "videos" / f"{slug}.mp4"),
    #     "category": "new",
    #     "game_name": metadata["game_name"],
    #     "genre": metadata["genre"],
    #     "frames": [],
    #     "script": "",
    #     "errors": [],
    # }
    # result = await graph.ainvoke(initial_state)

    # 데모용 더미 결과 (실제 구현 후 LangGraph 결과로 대체)
    result = {
        "slug": slug,
        "game_name": metadata["game_name"],
        "genre": metadata["genre"],
        "axis_scores": {
            "movement": {"score": 4.5, "rationale": "..."},
            "growth": {"score": 4.0, "rationale": "..."},
            "expansion": {"score": 4.5, "rationale": "..."},
            "camera": {"score": 4.0, "rationale": "..."},
            "color": {"score": 3.5, "rationale": "..."},
            "sound": {"score": 4.0, "rationale": "..."},
        },
        "grade": "strong",
        "weakest_axis": "color",
        "total_score": 24.5,
    }

    print(f"  [done] 처리 완료. 등급: {result['grade']}")
    return result


async def main() -> None:
    """메인 실행 함수."""
    print("=" * 60)
    print("CentLens 데모 캐시 사전 생성")
    print("=" * 60)

    DEMO_CACHE_DIR.mkdir(exist_ok=True)

    metadata_path = DATA_DIR / "metadata.json"
    if not metadata_path.exists():
        print("\n[error] data/metadata.json이 없습니다.")
        print("        먼저 python scripts/prepare_data.py를 실행하세요.")
        return

    metadata_list = json.loads(metadata_path.read_text(encoding="utf-8"))

    for video in metadata_list:
        slug = video["slug"]
        result = await precompute_video(slug, video)

        cache_path = DEMO_CACHE_DIR / f"{slug}.json"
        cache_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  캐시 저장: {cache_path}")

    print("\n" + "=" * 60)
    print(f"완료. {len(metadata_list)}개 영상의 데모 캐시 생성됨.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
