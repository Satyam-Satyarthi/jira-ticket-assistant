from ticket_assistant.agents.count import CountAgent
from ticket_assistant.agents.general import GeneralAgent
from ticket_assistant.agents.rag import RagAgent
from ticket_assistant.agents.registry import Registry


def build_registry():
    registry = Registry()
    for agent in (GeneralAgent(), CountAgent(), RagAgent()):
        registry.register(agent)
    return registry