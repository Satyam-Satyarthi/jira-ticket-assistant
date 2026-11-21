class Registry:
    def __init__(self):
        self.agents = {}

    def register(self, agent):
        self.agents[agent.name] = agent

    def get(self, name):
        return self.agents[name]

    def describe(self):
        return "\n".join(f"- {a.name}: {a.description}" for a in self.agents.values())