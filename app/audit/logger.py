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


        log = {

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


        self.logs.append(log)


        print(
            "\nAUDIT:",
            log
        )



    def get_logs(self):

        return self.logs
