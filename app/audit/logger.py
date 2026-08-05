from datetime import datetime


class AuditLogger:


    def __init__(self):

        self.logs = []



    def record(
        self,
        user,
        agent,
        tool,
        action,
        detail
    ):

        item = {

            "time":
                datetime.now().isoformat(),

            "user":
                user,

            "agent":
                agent,

            "tool":
                tool,

            "action":
                action,

            "detail":
                detail

        }


        self.logs.append(item)


        print(
            "AUDIT:",
            item
        )


        return item
