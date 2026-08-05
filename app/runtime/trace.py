from datetime import datetime


class RuntimeTrace:


    def __init__(self):

        self.steps = []



    def record(
        self,
        step,
        action,
        status,
        detail=None
    ):


        self.steps.append(

            {
                "step": step,

                "action": action,

                "status": status,

                "detail": detail,

                "time":
                    datetime.now()
                    .isoformat()

            }

        )



    def all(self):

        return self.steps
