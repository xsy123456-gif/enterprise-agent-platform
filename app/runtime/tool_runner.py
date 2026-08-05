from app.events.models import Event



class ToolRunner:


    def __init__(
        self,
        registry,
        permission,
        audit,
        event_bus
    ):


        self.registry = registry

        self.permission = permission

        self.audit = audit

        self.event_bus = event_bus



    def run(
        self,
        action,
        state
    ):


        tool_name = action.tool

        tool_input = action.input



        # =========================
        # Tool Call ID
        # =========================

        tool_call_id = state.add_tool_call(

            tool_name,

            tool_input

        )



        # =========================
        # Get Tool
        # =========================

        tool = self.registry.get(

            tool_name

        )


        if not tool:

            raise Exception(

                f"Tool not found: {tool_name}"

            )



        # =========================
        # Permission
        # =========================

        allowed = self.permission.check(

            state.role,

            tool_name

        )



        # =========================
        # Audit
        # =========================

        self.audit.record(

            user=state.user_id,

            agent="sales_agent",

            tool=tool_name,

            action=
            "allow" if allowed else "deny",

            detail=tool_input

        )



        if not allowed:

            raise Exception(

                "Permission denied"

            )



        # =========================
        # Execute Tool
        # =========================

        result = tool.execute(

            tool_input

        )



        # =========================
        # Event
        # =========================

        event = Event(

            event_type="tool_completed",

            payload={


                "user":

                    state.user_id,


                "agent":

                    "sales_agent",


                "tool":

                    tool_name,


                "input":

                    tool_input,


                "result":

                    result

            }

        )



        self.event_bus.publish(

            event

        )



        return result
