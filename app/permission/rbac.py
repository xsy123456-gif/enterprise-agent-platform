class PermissionManager:


    def __init__(self):

        self.permissions = {

            "sales":

            [
                "crm_query",
                "financial_query",
                "market_query",
            ],


            "manager":

            [
                "crm_query",
                "customer_update"
            ],


            "admin":

            [
                "*"
            ]

        }



    def check(
        self,
        role,
        tool
    ):

        allowed_tools = self.permissions.get(
            role,
            []
        )


        # admin 全部权限

        if "*" in allowed_tools:
            return True


        return tool in allowed_tools
