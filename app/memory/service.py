from app.memory.models import MemoryItem



class MemoryService:


    def __init__(
        self,
        storage
    ):

        self.storage = storage



    def save(
        self,
        memory_type,
        key,
        content
    ):


        memory = MemoryItem(

            memory_type,

            key,

            content

        )


        self.storage.save(
            memory
        )



    def recall(
        self,
        memory_type,
        key
    ):


        memories = self.storage.query(

            memory_type,

            key

        )


        return [

            m.to_dict()

            for m in memories

        ]
