from app.llm.prompts import SYSTEM_PROMPT



class AgentState:


    def __init__(
        self,
        task,
        user,
        role
    ):


        self.task = task

        self.user = user

        self.user_id = user

        self.role = role


        # Agent执行历史
        self.history=[]


        # 工具调用记录
        self.tool_calls=[]



    def add_tool_result(
        self,
        result
    ):


        self.history.append(

            {
                "role":"tool",

                "content":str(result)

            }

        )



    def add_tool_call(
        self,
        tool,
        input
    ):


        self.tool_calls.append(

            {
                "tool":tool,

                "input":input

            }

        )



    def generate_messages(
        self
    ):


        messages=[


            {
                "role":"system",

                "content":SYSTEM_PROMPT

            },


            {
                "role":"user",

                "content":self.task

            }

        ]


        messages.extend(
            self.history
        )


        return messages
