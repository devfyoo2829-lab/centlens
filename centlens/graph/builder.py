"""LangGraph StateGraph 조립.

흐름:
    START → ① preprocessor
          → [② movement, ③ growth, ④ expansion, ⑤ camera, ⑥ color, ⑦ sound] (병렬 분기)
          → ⑧ cross_check (6 judge가 모두 완료된 후 합류)
          → ⑨ grade_calculator
          → ⑩ embedder
          → END
"""

from langgraph.graph import END, START, StateGraph

from centlens.graph.nodes.camera_judge import camera_judge_node
from centlens.graph.nodes.color_judge import color_judge_node
from centlens.graph.nodes.cross_check import cross_check_node
from centlens.graph.nodes.embedder import embedder_node
from centlens.graph.nodes.expansion_judge import expansion_judge_node
from centlens.graph.nodes.grade_calculator import grade_calculator_node
from centlens.graph.nodes.growth_judge import growth_judge_node
from centlens.graph.nodes.movement_judge import movement_judge_node
from centlens.graph.nodes.preprocessor import preprocessor_node
from centlens.graph.nodes.sound_judge import sound_judge_node
from centlens.graph.state import CentLensState


JUDGE_NODES: tuple[str, ...] = (
    "movement_judge",
    "growth_judge",
    "expansion_judge",
    "camera_judge",
    "color_judge",
    "sound_judge",
)


def build_centlens_graph():
    """10개 노드를 가진 CentLens StateGraph를 컴파일하여 반환한다."""
    graph = StateGraph(CentLensState)

    graph.add_node("preprocessor", preprocessor_node)
    graph.add_node("movement_judge", movement_judge_node)
    graph.add_node("growth_judge", growth_judge_node)
    graph.add_node("expansion_judge", expansion_judge_node)
    graph.add_node("camera_judge", camera_judge_node)
    graph.add_node("color_judge", color_judge_node)
    graph.add_node("sound_judge", sound_judge_node)
    graph.add_node("cross_check", cross_check_node)
    graph.add_node("grade_calculator", grade_calculator_node)
    graph.add_node("embedder", embedder_node)

    graph.add_edge(START, "preprocessor")

    for axis_node in JUDGE_NODES:
        graph.add_edge("preprocessor", axis_node)
        graph.add_edge(axis_node, "cross_check")

    graph.add_edge("cross_check", "grade_calculator")
    graph.add_edge("grade_calculator", "embedder")
    graph.add_edge("embedder", END)

    return graph.compile()
