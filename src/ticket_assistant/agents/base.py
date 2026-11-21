from dataclasses import dataclass


@dataclass
class Context:
    store: object
    retriever: object


class Agent:
    name = ""
    description = ""

    def run(self, question, context):
        raise NotImplementedError


def result(agent, answer, **extra):
    return {"agent": agent.name, "answer": answer, **extra}