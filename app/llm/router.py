class LLMRouter:


    def __init__(
        self,
        providers
    ):

        self.providers=providers



    def select(
        self,
        task_type
    ):


        if task_type=="reasoning":

            return self.providers["deepseek"]


        if task_type=="local":

            return self.providers["r1"]


        return self.providers["qwen"]
