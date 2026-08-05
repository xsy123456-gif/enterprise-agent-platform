class MemoryStorage:


    def __init__(self):

        self.data = []



    def save(self, memory):

        self.data.append(
            memory
        )



    def query(
        self,
        memory_type,
        key
    ):


        result = []


        for item in self.data:


            if (
                item.memory_type == memory_type
                and
                item.key == key
            ):

                result.append(item)



        return result

