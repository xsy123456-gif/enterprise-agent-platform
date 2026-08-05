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


        # =========================
        # Identity
        # =========================

        self.user_id = user_id

        self.role = role

        self.agent_name = agent_name



        # =========================
        # Task
        # =========================

        self.task = task



        # =========================
        # Session
        # =========================

        self.session_id = str(
            uuid.uuid4()
        )


        self.trace_id = str(
            uuid.uuid4()
        )



        # =========================
        # Conversation Messages
        # =========================

        self.messages = []


        self.messages.append(

            {
                "role":
                    "user",

                "content":
                    task

            }

        )



        # =========================
        # Memory
        # =========================

        self.memory_context = []



        # =========================
        # Tool
        # =========================

        self.tool_results = []

        self.tool_calls = []

        self.last_tool_call_id = None



        # =========================
        # Metadata
        # =========================

        self.created_at = (

            datetime.now()
            .isoformat()

        )



    # =================================================
    # Add Assistant Tool Call
    #
    # user
    #   |
    # assistant(tool_calls)
    #   |
    # tool(result)
    #
    # =================================================

    def add_tool_call(
        self,
        tool,
        input,
        tool_call_id=None
    ):


        if tool_call_id is None:

            tool_call_id = (

                "call_"

                + tool

            )



        assistant_message = {


            "role":

                "assistant",


            "content":

                None,


            "tool_calls":

            [

                {

                    "id":

                        tool_call_id,


                    "type":

                        "function",


                    "function":

                    {

                        "name":

                            tool,


                        "arguments":

                            str(

                                {

                                    "input":

                                        input

                                }

                            )

                    }

                }

            ]

        }



        self.messages.append(

            assistant_message

        )



        self.tool_calls.append(

            {


                "id":

                    tool_call_id,


                "tool":

                    tool,


                "input":

                    input


            }

        )



        self.last_tool_call_id = tool_call_id



        return tool_call_id




    # =================================================
    # Add Tool Result
    #
    # role=tool
    # 必须对应 tool_call_id
    #
    # =================================================

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




    # =================================================
    # Normal Message
    # =================================================

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
