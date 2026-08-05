from datetime import datetime
import uuid



class AgentContext:


    def __init__(
        self,
        task,
        user_id,
        role,
        agent_name
    ):


        self.user_id = user_id

        self.role = role

        self.agent_name = agent_name


        self.task = task


        self.session_id = str(
            uuid.uuid4()
        )


        self.trace_id = str(
            uuid.uuid4()
        )


        # LLM messages

        self.messages = [

            {
                "role":"user",
                "content":task
            }

        ]


        self.tool_results = []


        self.last_tool_call_id = None



    def add_tool_call(
        self,
        tool_name,
        input
    ):

        tool_call_id = (
            "call_"
            +
            str(uuid.uuid4())
        )


        self.last_tool_call_id = tool_call_id


        self.messages.append(

            {
                "role":"assistant",

                "tool_calls":[

                    {

                        "id":
                            tool_call_id,

                        "type":
                            "function",

                        "function":{

                            "name":
                                tool_name,

                            "arguments":
                                str(input)

                        }

                    }

                ]

            }

        )


        return tool_call_id



    def add_tool_result(
        self,
        tool_call_id,
        result
    ):


        self.tool_results.append(
            result
        )


        self.messages.append(

            {

                "role":
                    "tool",

                "tool_call_id":
                    tool_call_id,

                "content":
                    str(result)

            }

        )



    def add_message(
        self,
        role,
        content
    ):


        self.messages.append(

            {

                "role":
                    role,

                "content":
                    content

            }

        )
