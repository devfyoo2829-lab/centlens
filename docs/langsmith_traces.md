# LangSmith Trace 자산

CentLens LangGraph 10노드 파이프라인을 슈퍼센트 자체 광고 영상 5편에 적용한 실행 트레이스.
각 영상은 root run 1개 + 노드별 child run 10개로 구성되며, 6축 채점의 토큰 소비·레이턴시·프롬프트·응답 원문을 LangSmith UI에서 직접 시연 가능하다.

- **프로젝트**: `centlens` (id `68d3bf17-fbe9-4e10-b341-aca113089018`)
- **실행 일시**: 2026-04-27 20:05 UTC
- **재현 방법**: `python scripts/precompute_demo.py` (영상별로 `run_name=centlens:{slug}`, `tags=[centlens, precompute_demo, {slug}, {category}]`로 식별)

---

## Trace 5건

| 영상 | 분류 | 등급 | total | weakest | 처리시간 | LangSmith |
|---|---|---|---:|---|---:|---|
| Burger Please | new | weak | 21.80 | growth | 82.5s | [Open](https://smith.langchain.com/o/_/projects/p/68d3bf17-fbe9-4e10-b341-aca113089018/r/019dd08c-04fc-7c11-a546-b7ded709db6b) |
| Pizza Ready | new | weak | 23.15 | growth | 69.3s | [Open](https://smith.langchain.com/o/_/projects/p/68d3bf17-fbe9-4e10-b341-aca113089018/r/019dd08d-476f-7f53-9788-dbbe68227125) |
| Snake Clash | new | weak | 21.60 | sound | 33.4s | [Open](https://smith.langchain.com/o/_/projects/p/68d3bf17-fbe9-4e10-b341-aca113089018/r/019dd08e-5648-7fe1-aef9-22e8491c414b) |
| Twerk Race 3D | competitor | weak | 21.25 | sound | 33.2s | [Open](https://smith.langchain.com/o/_/projects/p/68d3bf17-fbe9-4e10-b341-aca113089018/r/019dd08e-d8af-75f1-8005-a642e253819e) |
| Kingshot | competitor | weak | 22.05 | sound | 66.8s | [Open](https://smith.langchain.com/o/_/projects/p/68d3bf17-fbe9-4e10-b341-aca113089018/r/019dd08f-5a60-7310-bbca-bc8c29775140) |

URL의 `/o/_/`는 본인 organization slug로 자동 redirect된다.

---

## 영상별 시연 포인트

각 영상은 Annie 글이 명시적으로 인용한 사례로, 블로그 글 자체가 채점 정확도의 reference가 된다.

- **Burger Please** — Annie 글이 "절단 움직임 + 대량 오브젝트" 사례로 인용한 영상. **Movement final=4.35**(5편 중 최고 tied)로 그 인용을 정량적으로 지지. 동시에 growth A=3.5 vs B=2.0(diff=1.5) — A는 "100 burgers" 수치 증가를 성장으로 봤지만 B는 캐릭터 외형 변화 부재를 지적, **Annie 글의 성장 정의("플레이어가 변화하는 장면")에 B가 더 충실**한 사례.
- **Pizza Ready** — Annie 글이 "유리병 굴리기 + 파편" 사례로 인용. **total=23.15로 5편 중 최고**지만 growth=2.85가 발목을 잡아 weak 등급. **weakest-link 정책의 의도**(한 축만 높은 영상이 과대평가되는 것 방지)를 정확히 보여주는 시연 자산.
- **Snake Clash** — Annie 글이 "시작 3초 만에 외형 변화" 사례로 인용. **Growth final=4.35로 5편 중 최고** — 인용과 정량 정합. 스크립트 0자(무음 영상)에도 프레임만으로 성장 축을 정확히 짚어내 멀티모달 평가의 강점 시연.
- **Twerk Race 3D** — Annie 글이 "게이트 통과 신체 변화" 사례로 인용한 외부 경쟁사 영상. **expansion 축 A=3.8 vs B=2.0 (diff=1.8) — A/B 시각 차이 시연 1순위**. A는 ±점수 게이트를 시스템 확장으로 봤지만 B는 "런웨이 구조 일정 유지"로 반박. STT가 환각으로 판정되어 빈 문자열로 대체된 사례이기도 함(필터 동작 시연).
- **Kingshot** — Annie 글이 "자원 → 타워 확장" 사례로 인용한 외부 경쟁사 영상. **Expansion final=4.1**로 인용과 정합. 거의 무음(20자 STT)임에도 시각만으로 확장축을 정량화. **Cross-Check가 43초로 가장 무거운 트레이스** — 6축 일괄 평가의 비용 vs 편향 제거 트레이드오프 시연 자산.

---

## A/B 시각 차이 사례 (Position Bias 제거의 시연 가치)

A·B 점수 차이 ≥ 1.0인 축은 면접에서 "Cross-Check가 단순 점수 평균이 아니라 두 관점의 평균"임을 보여주는 자산이다.

| 영상 | 축 | A | B | final | 시각 차이 요약 |
|---|---|---:|---:|---:|---|
| Twerk Race 3D | expansion | 3.80 | 2.00 | 2.90 | A: 단계별 ±점수 선택지 = 시스템 확장 / B: 런웨이 구조 일정, 확장 없음 |
| Twerk Race 3D | sound | 2.00 | 3.50 | 2.75 | 무음 영상의 사운드 평가 갈림 |
| Burger Please | growth | 3.50 | 2.00 | 2.75 | A: "100 burgers" 수치 증가 = 성장 / B: 캐릭터 외형 변화 부재 |
| Snake Clash | expansion | 3.80 | 2.50 | 3.15 | 같은 영상에 대한 확장 정의 해석 차이 |
| Twerk Race 3D | movement | 4.20 | 3.00 | 3.60 | 게이트 통과 동작의 "물리적 반응" 강도 평가 |
| Burger Please | expansion | 4.20 | 3.00 | 3.60 | "100 burgers" 표시를 시스템 확장으로 볼지 단순 카운터로 볼지 |
| Snake Clash | sound | 2.00 | 3.00 | 2.50 | 무음 영상의 효과음 시각 단서 평가 |

---

## LangSmith UI에서 볼 수 있는 것

각 trace를 열면 다음이 펼쳐진다.

- **노드별 child run** 10개 (preprocessor → 6 judge 병렬 → cross_check → grade → embedder)
- 각 LLM 호출의 **input messages**(프롬프트 전문 + base64 프레임 5장 + 스크립트)와 **output**(JSON 응답 원문)
- **토큰 사용량**(input/output) — 영상당 비용 산출 근거
- **레이턴시 분포** — 6 judge 병렬 fan-out + cross_check fan-in의 실제 wall time
- **에러 추적** — JSON 파싱 실패 등 발생 시 해당 노드만 격리해 재현 가능

면접 시연 시 추천 흐름:
1. Twerk Race 3D trace에서 expansion judge의 A 응답 → cross_check의 B 응답 → 최종 평균을 한 화면에서 펼쳐 보이기
2. Kingshot trace에서 cross_check 노드 단독으로 클릭해 6축 일괄 평가 응답 JSON과 토큰 사용량 시연
3. Snake Clash trace에서 preprocessor의 STT=0자 + Movement Judge가 프레임만으로 평가한 input messages 시연 (멀티모달 강점)
