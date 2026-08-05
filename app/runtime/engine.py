class RuntimeEngine:


    def __init__(
        self,
        executor
    ):

        self.executor = executor



    def run(
        self,
        state
    ):

        return self.executor.run(
            state
        )
