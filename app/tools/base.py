from abc import ABC,abstractmethod



class BaseTool(ABC):


    name=None


    @abstractmethod
    def execute(self,input):
        pass
