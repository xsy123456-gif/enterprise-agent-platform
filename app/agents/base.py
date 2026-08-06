from abc import ABC, abstractmethod



class BaseAgent(ABC):


    name = None



    def __init__(
        self,
        llm,
        agent_id=None,
        version=None
    ):

        self.llm = llm

        self.agent_id = agent_id

        self.version = version



    def reason(self, messages):
        """Compatibility hook; the execution loop normally calls ``llm``."""
        return self.llm.chat(messages)
