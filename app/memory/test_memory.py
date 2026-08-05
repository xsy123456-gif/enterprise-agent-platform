from app.memory.storage import MemoryStorage

from app.memory.service import MemoryService



storage = MemoryStorage()


memory = MemoryService(
    storage
)



memory.save(

    "customer",

    "Tesla",

    {
        "industry":
        "新能源汽车",

        "interest":
        "产品B"
    }

)



result = memory.recall(

    "customer",

    "Tesla"

)


print(result)
