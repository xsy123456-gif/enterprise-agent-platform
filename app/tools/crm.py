from app.tools.base import BaseTool


class CRMTool(BaseTool):
    name = "crm_query"
    description = "查询客户信息"
    input_schema = {
        "type": "object",
        "properties": {"customer": {"type": "string", "description": "客户标识，例如 customer_A"}},
        "required": ["customer"],
    }

    def validate_input(self, customer_id):
        if isinstance(customer_id, dict):
            customer_id = customer_id.get("customer")
        return isinstance(customer_id, str) and bool(customer_id.strip())

    def execute(self, customer_id):
        if isinstance(customer_id, dict):
            customer_id = customer_id.get("customer")

        customers = {
            "customer_A": {
                "name": "Tesla",
                "industry": "新能源汽车",
                "history": [
                    "去年购买产品A",
                    "近期关注产品B",
                ],
            }
        }
        aliases = {"A": "customer_A", "客户A": "customer_A"}
        return customers.get(aliases.get(customer_id, customer_id), "客户不存在")
