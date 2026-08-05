from app.memory.types import CUSTOMER



class MemoryWorker:


    def __init__(
        self,
        memory
    ):

        self.memory = memory



    def process(
        self,
        event
    ):


        payload = event.payload


        if payload["tool"] != "crm_query":

            return



        customer = payload["result"]



        self.memory.save(

            CUSTOMER,

            customer["name"],

            {

                "industry":

                customer["industry"],


                "history":

                customer["history"]

            }

        )


        print(
            "Memory Updated:"
        )

        print(customer["name"])
