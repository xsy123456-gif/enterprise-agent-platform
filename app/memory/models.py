from datetime import datetime



class MemoryItem:


    def __init__(
        self,
        memory_type,
        key,
        content
    ):


        self.memory_type = memory_type

        self.key = key

        self.content = content

        self.created_at = datetime.now().isoformat()



    def to_dict(self):

        return {

            "type":
            self.memory_type,


            "key":
            self.key,


            "content":
            self.content,


            "created_at":
            self.created_at

        }
