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



            action = self.agent.think(

                state

            )



            print(

                "\nACTION:",

                action

            )



            # =====================
            # Finish
            # =====================

            if action.type == "finish":


                return action.output



            # =====================
            # Tool
            # =====================

            if action.type == "tool":


                result = self.tool_runner.run(

                    action,

                    state

                )



                state.add_tool_result(

                    state.last_tool_call_id,

                    result

                )



                continue



        return {

            "error":

                "Agent exceeded max steps"

        }
