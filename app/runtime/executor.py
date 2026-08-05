from app.runtime.action import AgentAction



class AgentExecutor:


    def __init__(
        self,
        agent,
        tool_runner,
        max_steps=10
    ):

        self.agent = agent

        self.tool_runner = tool_runner

        self.max_steps = max_steps



    def run(
        self,
        state
    ):


        step = 0


        while step < self.max_steps:


            step += 1



            # ======================
            # Think
            # ======================

            action = self.agent.think(

                state

            )


            print(

                "ACTION:",

                action

            )



            # ======================
            # Finish
            # ======================

            if action.type == AgentAction.FINISH:


                return action.output



            # ======================
            # Tool
            # ======================

            if action.type == AgentAction.TOOL:


                self.tool_runner.run(

                    action,

                    state

                )


                continue



        return {

            "error":

            "Agent exceeded max steps"

        }
