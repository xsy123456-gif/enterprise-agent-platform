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



    @abstractmethod
    def think(
        self,
        context
    ):

        pass
