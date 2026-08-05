class CRMTool:


    name = "crm_query"


    description = "查询客户信息"


    def execute(self, customer_id):

        customers = {

            "customer_A": {

                "name": "Tesla",

                "industry": "新能源汽车",

                "history": [
                    "去年购买产品A",
                    "近期关注产品B"
                ]

            }

        }


        return customers.get(
            customer_id,
            "客户不存在"
        )
