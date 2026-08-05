from app.runtime.parser import AgentOutputParser
from app.llm.prompts import SYSTEM_PROMPT



class SalesAgent:


    def __init__(
        self,
        llm
    ):

        self.llm = llm

        self.parser = AgentOutputParser()



    def think(
        self,
        state
    ):


        messages = [

            {
                "role":"system",
                "content":SYSTEM_PROMPT
            }

        ]


        messages.extend(

            state.messages

        )


        response = self.llm.chat(

            messages

        )


        print(

            "\nLLM RESPONSE:",

            response

        )


        action = self.parser.parse(

            response

        )


        return action
