class RBAC:


    def __init__(self):

        self.roles = {


            "sales_rep":[
                "crm_query"
            ],


            "sales_manager":[
                "crm_query"
            ],


            "admin":[
                "*"
            ]

        }



    def check(
        self,
        role,
        tool_name
    ):


        permissions = self.roles.get(
            role,
            []
        )


        if "*" in permissions:

            return True


        return tool_name in permissions
