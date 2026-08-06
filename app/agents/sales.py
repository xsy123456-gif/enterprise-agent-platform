import json


from app.agents.base import BaseAgent


from app.runtime.action import AgentAction


from app.llm.prompts import SYSTEM_PROMPT





class SalesAgent(BaseAgent):


    def __init__(
        self,
        llm,
        agent_id="sales_agent",
        version=None
    ):

        super().__init__(
            llm=llm,
            agent_id=agent_id,
            version=version
        )



    def think(
        self,
        state
    ):


        messages = []


        # =========================
        # System Prompt
        # =========================

        messages.append(

            {

                "role":
                    "system",

                "content":
                    SYSTEM_PROMPT

            }

        )



        # =========================
        # Conversation History
        # =========================

        messages.extend(

            state.messages

        )



        # =========================
        # Tool Result History
        # =========================

        response = self.llm.chat(

            messages

        )



        print()

        print(
            "LLM RESPONSE:",
            response
        )



        # =========================
        # Parse JSON
        # =========================

        if isinstance(response, str):

            data = json.loads(

                response

            )

        else:

            data = response



        # =========================
        # Tool Action
        # =========================

        if data.get("type") == "tool":


            return AgentAction(

                type=
                    AgentAction.TOOL,

                tool=
                    data["tool"],

                input=
                    data["input"]

            )



        # =========================
        # Finish Action
        # =========================

        if data.get("type") == "finish":


            state.add_message(

                "assistant",

                data["output"]

            )


            return AgentAction(

                type=
                    AgentAction.FINISH,

                output=
                    data["output"]

            )



        raise Exception(

            "Invalid LLM response"

        )
