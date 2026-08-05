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
        # Trace
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



        # =========================
        # Memory
        # =========================

        self.memory_context = []



        # =========================
        # Tool Runtime
        # =========================

        self.tool_results = []


        self.last_tool_call_id = None

        self.last_tool_name = None

        self.last_tool_input = None



        # =========================
        # Metadata
        # =========================

        self.created_at = (
            datetime.now()
            .isoformat()
        )



    # =================================================
    # Message Management
    # =================================================


    def add_message(
        self,
        role,
        content
    ):

        self.messages.append(

            {
                "role": role,

                "content": content
            }

        )



    # =================================================
    # Tool Call
    #
    # called by ToolRunner
    #
    # =================================================


    def add_tool_call(
        self,
        tool_name,
        tool_input
    ):


        tool_call_id = str(
            uuid.uuid4()
        )


        self.last_tool_call_id = tool_call_id

        self.last_tool_name = tool_name

        self.last_tool_input = tool_input



        self.messages.append(

            {

                "role": "assistant",


                "tool_calls": [

                    {

                        "id": tool_call_id,


                        "type": "function",


                        "function": {


                            "name": tool_name,


                            "arguments": str(tool_input)

                        }

                    }

                ]

            }

        )


        return tool_call_id



    # =================================================
    # Tool Result
    #
    # called after tool execution
    #
    # =================================================


    def add_tool_result(
        self,
        tool_call_id,
        result
    ):


        self.tool_results.append(

            {

                "tool_call_id": tool_call_id,

                "result": result

            }

        )



        self.messages.append(

            {

                "role": "tool",


                "tool_call_id": tool_call_id,


                "content": str(result)

            }

        )



    # =================================================
    # LLM Input
    # =================================================


    def get_messages(
        self
    ):

        return self.messages



    # =================================================
    # Debug
    # =================================================


    def snapshot(
        self
    ):

        return {

            "session_id": self.session_id,

            "trace_id": self.trace_id,

            "user_id": self.user_id,

            "agent": self.agent_name,

            "messages": self.messages,

            "tools": self.tool_results

        }
