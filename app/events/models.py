from datetime import datetime


class Event:


    def __init__(
        self,
        event_type,
        payload
    ):


        self.event_type = event_type

        self.payload = payload

        self.created_at = datetime.now().isoformat()



    def to_dict(self):

        return {

            "type":
            self.event_type,

            "payload":
            self.payload,

            "created_at":
            self.created_at

        }
