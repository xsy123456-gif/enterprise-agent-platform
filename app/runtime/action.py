class AgentAction:


    TOOL = "tool"

    FINISH = "finish"



    def __init__(
        self,
        type,
        tool=None,
        input=None,
        output=None,
        tool_call_id=None
    ):

        self.type = type

        self.tool = tool

        self.input = input

        self.output = output

        self.tool_call_id = tool_call_id



    @staticmethod
    def tool_action(
        tool,
        input
    ):

        return AgentAction(

            type=AgentAction.TOOL,

            tool=tool,

            input=input,

            tool_call_id="call_" + tool

        )



    @staticmethod
    def finish_action(
        output
    ):

        return AgentAction(

            type=AgentAction.FINISH,

            output=output

        )



    def __repr__(self):

        return (
            f"AgentAction("
            f"type={self.type}, "
            f"tool={self.tool}, "
            f"input={self.input}, "
            f"output={self.output})"
        )
