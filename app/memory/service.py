from app.memory.models import MemoryItem



class MemoryService:


    def __init__(
        self,
        storage
    ):

        self.storage = storage



    def save(self, *args, **kwargs):
        if kwargs and {"user_id", "agent_id", "memory_type", "scope", "content"} <= set(kwargs):
            memory_type = kwargs["memory_type"]
            key = self._scoped_key(kwargs["user_id"], kwargs["agent_id"], kwargs["scope"])
            content = kwargs["content"]
        elif len(args) == 5:
            user_id, agent_id, memory_type, scope, content = args
            key = self._scoped_key(user_id, agent_id, scope)
        elif len(args) == 3:
            memory_type, key, content = args
        else:
            raise TypeError("save expects legacy (memory_type, key, content) or scoped memory arguments")


        memory = MemoryItem(

            memory_type,

            key,

            content

        )


        self.storage.save(
            memory
        )

        return memory



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

    def retrieve(self, user_id, agent_id, scope, memory_type):
        return self.recall(memory_type, self._scoped_key(user_id, agent_id, scope))

    @staticmethod
    def _scoped_key(user_id, agent_id, scope):
        return (user_id, agent_id, scope)
