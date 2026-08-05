import json

from app.runtime.action import AgentAction



class AgentOutputParser:


    def parse(
        self,
        response
    ):

        try:

            data = json.loads(
                response
            )


        except json.JSONDecodeError:

            return AgentAction.finish_action(
                output=response
            )


        action_type = data.get(
            "type"
        )


        if action_type == AgentAction.TOOL:


            return AgentAction.tool_action(

                tool=data.get(
                    "tool"
                ),

                input=data.get(
                    "input"
                )

            )


        elif action_type == AgentAction.FINISH:


            return AgentAction.finish_action(

                output=data.get(
                    "output"
                )

            )


        else:


            return AgentAction.finish_action(

                output=response

            )
