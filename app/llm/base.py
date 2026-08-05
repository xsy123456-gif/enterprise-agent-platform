from abc import ABC, abstractmethod



class BaseLLM(ABC):


    provider = None

    model = None



    @abstractmethod
    def chat(
        self,
        messages,
        **kwargs
    ):
        pass
