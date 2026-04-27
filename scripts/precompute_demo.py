"""데모 캐시 사전 생성 스크립트.

prepare_data.py로 준비된 5편 영상에 대해 LangGraph 전체 흐름(10개 노드)을 실행하고,
결과를 demo_cache/{slug}.json에 저장한다. 임베딩 벡터(1536차원)는 파일이 커지므로
demo_cache/{slug}_embedding.json에 별도로 분리 저장한다.

사용법:
    python scripts/precompute_demo.py                   # 5편 모두
    python scripts/precompute_demo.py --slug pizza_ready_break   # 1편만 시범 실행

사전 요구사항:
    - python scripts/prepare_data.py 완료 (data/videos/*.mp4 + data/metadata.json)
    - .env 파일에 ANTHROPIC_API_KEY, OPENAI_API_KEY 설정
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(_PROJECT_ROOT / ".env")

from centlens.graph.builder import build_centlens_graph  # noqa: E402

DATA_DIR = _PROJECT_ROOT / "data"
VIDEOS_DIR = DATA_DIR / "videos"
DEMO_CACHE_DIR = _PROJECT_ROOT / "demo_cache"

AXES: tuple[str, ...] = ("movement", "growth", "expansion", "camera", "color", "sound")
JUDGE_NODES: tuple[str, ...] = tuple(f"{ax}_judge" for ax in AXES)

# 영상 1편당 추정 비용 — docs/03_ai_tools.md (Whisper + 6 Judge + Cross-Check + Embed)
EST_COST_PER_VIDEO_USD: float = 0.12


def _setup_logging() -> None:
    """노드 INFO 로그를 stdout으로 흘려보낸다 (실시간 진행 확인용)."""
    logging.basicConfig(
        level=logging.INFO,
        format="    %(message)s",
        stream=sys.stdout,
        force=True,
    )
    # langgraph/openai/anthropic의 노이즈 로그는 WARNING으로 억제
    for noisy in ("httpx", "httpcore", "openai", "anthropic", "langgraph"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _check_prerequisites(metadata_list: list[dict]) -> tuple[bool, list[str]]:
    """API 키 + 영상 파일 존재 여부를 확인한다."""
    issues: list[str] = []
    if not os.getenv("ANTHROPIC_API_KEY"):
        issues.append("ANTHROPIC_API_KEY 누락 — .env 확인")
    if not os.getenv("OPENAI_API_KEY"):
        issues.append("OPENAI_API_KEY 누락 — .env 확인")
    for v in metadata_list:
        path = VIDEOS_DIR / f"{v['slug']}.mp4"
        if not path.is_file():
            issues.append(f"영상 파일 없음: {path} — prepare_data.py 먼저 실행")
    return (len(issues) == 0), issues


def _derive_b_score(
    a: Optional[dict], final: Optional[dict]
) -> Optional[dict]:
    """A·final로부터 B를 역산. final = (a + b) / 2 → b = 2*final - a.

    a 또는 final이 없으면 None. rationale은 재구성 표기.
    """
    if a is None or final is None:
        return None
    try:
        b_score = round(2 * float(final["score"]) - float(a["score"]), 2)
        b_conf = round(2 * float(final["confidence"]) - float(a["confidence"]), 2)
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "score": b_score,
        "rationale": "(B채점 — A점수와 final로부터 역산)",
        "confidence": b_conf,
    }


async def _run_one(slug: str, metadata: dict, compiled: Any) -> dict:
    """단일 영상에 대해 그래프 실행 + 노드별 시간 측정 + 결과 dict 구성."""
    print(f"\n[{slug}] {metadata['game_name']} ({metadata['genre']}) — 처리 시작")
    started_wall = time.time()
    started = time.perf_counter()

    initial_state: dict[str, Any] = {
        "video_path": str(VIDEOS_DIR / f"{slug}.mp4"),
        "category": metadata["category"],
        "game_name": metadata["game_name"],
        "genre": metadata["genre"],
        "errors": [],
    }

    node_end_t: dict[str, float] = {}
    final_state: dict[str, Any] = dict(initial_state)
    fatal_error: Optional[str] = None

    try:
        async for chunk in compiled.astream(initial_state, stream_mode="updates"):
            now = time.perf_counter() - started
            if not isinstance(chunk, dict):
                continue
            for node_name, update in chunk.items():
                node_end_t[node_name] = now
                if isinstance(update, dict):
                    for k, v in update.items():
                        final_state[k] = v
    except Exception as e:
        fatal_error = f"그래프 실행 중단: {type(e).__name__}: {e}"
        print(f"  [error] {fatal_error}")

    total_elapsed = time.perf_counter() - started

    # ── 노드별 소요시간 산출 ────────────────────────────────────────────
    durations: dict[str, Optional[float]] = {}
    durations["preprocessor"] = node_end_t.get("preprocessor")

    pre_t = node_end_t.get("preprocessor")
    if pre_t is not None:
        for jn in JUDGE_NODES:
            jt = node_end_t.get(jn)
            durations[jn] = round(jt - pre_t, 3) if jt is not None else None
    else:
        for jn in JUDGE_NODES:
            durations[jn] = None

    judge_end_ts = [node_end_t[jn] for jn in JUDGE_NODES if jn in node_end_t]
    cc_t = node_end_t.get("cross_check")
    if cc_t is not None and judge_end_ts:
        durations["cross_check"] = round(cc_t - max(judge_end_ts), 3)
    else:
        durations["cross_check"] = None

    gc_t = node_end_t.get("grade_calculator")
    if gc_t is not None and cc_t is not None:
        durations["grade_calculator"] = round(gc_t - cc_t, 3)
    else:
        durations["grade_calculator"] = None

    em_t = node_end_t.get("embedder")
    if em_t is not None and gc_t is not None:
        durations["embedder"] = round(em_t - gc_t, 3)
    else:
        durations["embedder"] = None

    if durations["preprocessor"] is not None:
        durations["preprocessor"] = round(durations["preprocessor"], 3)

    # ── 6축 점수: A / B(역산) / final ───────────────────────────────────
    axis_scores: dict[str, dict] = {}
    for ax in AXES:
        a = final_state.get(f"{ax}_a")
        f = final_state.get(f"{ax}_final")
        axis_scores[ax] = {
            "a": a,
            "b": _derive_b_score(a, f),
            "final": f,
        }

    embedding_vec = final_state.get("embedding")

    result: dict[str, Any] = {
        "slug": slug,
        "metadata": {
            "game_name": metadata["game_name"],
            "genre": metadata["genre"],
            "category": metadata["category"],
            "publisher": metadata.get("publisher"),
        },
        "axis_scores": axis_scores,
        "grade": final_state.get("grade"),
        "weakest_axis": final_state.get("weakest_axis"),
        "total_score": final_state.get("total_score"),
        "durations_sec": durations,
        "total_elapsed_sec": round(total_elapsed, 2),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(started_wall)),
        "errors": list(final_state.get("errors") or []) + (
            [fatal_error] if fatal_error else []
        ),
        "embedding_dim": len(embedding_vec) if embedding_vec else None,
    }

    DEMO_CACHE_DIR.mkdir(exist_ok=True)
    cache_path = DEMO_CACHE_DIR / f"{slug}.json"
    cache_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if embedding_vec:
        emb_path = DEMO_CACHE_DIR / f"{slug}_embedding.json"
        emb_path.write_text(
            json.dumps({"slug": slug, "embedding": embedding_vec}),
            encoding="utf-8",
        )

    grade = result["grade"] or "—"
    total = result["total_score"]
    total_str = f"{total:.2f}" if isinstance(total, (int, float)) else "—"
    err_count = len(result["errors"])
    print(
        f"  [done] {slug}: 등급={grade}, 합계={total_str}, "
        f"소요={total_elapsed:.1f}초, 에러={err_count}"
    )
    return result


def _print_summary(results: list[dict]) -> None:
    """결과 요약 표 출력."""
    if not results:
        return
    print("\n" + "=" * 92)
    print("결과 요약")
    print("=" * 92)
    print(f"{'게임명':<20} {'등급':<8} {'합계':>6}  {'최약축':<12} {'소요(s)':>7}  에러")
    print("-" * 92)
    for r in results:
        game = (r.get("metadata") or {}).get("game_name") or r.get("slug") or "?"
        grade = r.get("grade") or "—"
        total = r.get("total_score")
        total_str = f"{total:.2f}" if isinstance(total, (int, float)) else "—"
        weakest = r.get("weakest_axis") or "—"
        elapsed = r.get("total_elapsed_sec")
        elapsed_str = f"{elapsed:.1f}" if isinstance(elapsed, (int, float)) else "—"
        err_count = len(r.get("errors") or [])
        err_flag = "X" if err_count else "-"
        print(
            f"{game:<20} {grade:<8} {total_str:>6}  {weakest:<12} "
            f"{elapsed_str:>7}  {err_flag} ({err_count})"
        )
    print("=" * 92)


async def _async_main(slug_filter: Optional[str]) -> int:
    _setup_logging()
    print("=" * 60)
    print("CentLens 데모 캐시 사전 생성")
    print("=" * 60)

    metadata_path = DATA_DIR / "metadata.json"
    if not metadata_path.exists():
        print("\n[error] data/metadata.json이 없습니다.")
        print("        먼저 python scripts/prepare_data.py를 실행하세요.")
        return 1

    metadata_list: list[dict] = json.loads(metadata_path.read_text(encoding="utf-8"))
    if slug_filter:
        metadata_list = [v for v in metadata_list if v["slug"] == slug_filter]
        if not metadata_list:
            print(f"\n[error] --slug={slug_filter}에 해당하는 영상이 metadata.json에 없습니다.")
            return 1

    ok, issues = _check_prerequisites(metadata_list)
    if not ok:
        print("\n[error] 사전 요구사항 미충족:")
        for msg in issues:
            print(f"  - {msg}")
        return 1

    n = len(metadata_list)
    print(f"\n처리 대상: {n}편 영상")
    print(f"추정 비용: 약 ${n * EST_COST_PER_VIDEO_USD:.2f} (영상당 ~${EST_COST_PER_VIDEO_USD})")
    print(f"출력: {DEMO_CACHE_DIR}/")

    compiled = build_centlens_graph()
    print("LangGraph 컴파일 OK (10노드)")

    results: list[dict] = []
    for video in metadata_list:
        try:
            r = await _run_one(video["slug"], video, compiled)
        except Exception as e:
            print(f"  [fatal] {video['slug']} 처리 실패: {e}")
            r = {
                "slug": video["slug"],
                "metadata": {
                    "game_name": video["game_name"],
                    "genre": video["genre"],
                    "category": video["category"],
                    "publisher": video.get("publisher"),
                },
                "errors": [f"치명적 오류: {type(e).__name__}: {e}"],
            }
        results.append(r)

    _print_summary(results)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CentLens 데모 캐시 사전 생성")
    parser.add_argument(
        "--slug",
        type=str,
        default=None,
        help="특정 슬러그 1편만 실행 (예: burger_please_drive_thru). 미지정 시 5편 모두.",
    )
    args = parser.parse_args()
    return asyncio.run(_async_main(args.slug))


if __name__ == "__main__":
    raise SystemExit(main())
