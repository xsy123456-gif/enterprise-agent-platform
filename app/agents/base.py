from abc import ABC, abstractmethod



class BaseAgent(ABC):


    name = None



    def __init__(
        self,
        llm
    ):

        self.llm = llm



    @abstractmethod
    def think(
        self,
        context
    ):

        pass
