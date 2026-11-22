from ticket_assistant.agents.chart import ChartAgent
from ticket_assistant.agents.count import CountAgent
from ticket_assistant.agents.general import GeneralAgent
from ticket_assistant.agents.rag import RagAgent
from ticket_assistant.agents.registry import Registry
from ticket_assistant.agents.table import TableAgent
from ticket_assistant.agents.analysis import AnalysisAgent


def build_registry():
    registry = Registry()
    for agent in (GeneralAgent(), CountAgent(), TableAgent(), ChartAgent(), AnalysisAgent(), RagAgent()):
        registry.register(agent)
    return registry