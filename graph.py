from langgraph.graph import StateGraph, END

from state import WarRoomState
from agents import (
    data_analyst_node,
    pm_node,
    marketing_node,
    risk_node,
    orchestrator_node
)


def build_graph() -> StateGraph:
    graph = StateGraph(WarRoomState)

    graph.add_node("data_analyst", data_analyst_node)
    graph.add_node("pm", pm_node)
    graph.add_node("marketing", marketing_node)
    graph.add_node("risk", risk_node)
    graph.add_node("orchestrator", orchestrator_node)

    graph.set_entry_point("data_analyst")

    graph.add_edge("data_analyst", "pm")
    graph.add_edge("pm", "marketing")
    graph.add_edge("marketing", "risk")
    graph.add_edge("risk", "orchestrator")
    graph.add_edge("orchestrator", END)

    return graph.compile()

