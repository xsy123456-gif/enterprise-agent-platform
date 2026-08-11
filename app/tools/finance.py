from app.tools.base import BaseTool


class FinancialTool(BaseTool):
    name = "financial_query"
    description = "查询客户财务信息"
    input_schema = {
        "type": "object",
        "properties": {"customer": {"type": "string", "description": "客户标识，例如 customer_A"}},
        "required": ["customer"],
    }

    def validate_input(self, value):
        if isinstance(value, dict):
            value = value.get("customer")
        return isinstance(value, str) and bool(value.strip())

    def execute(self, value):
        customer = value.get("customer") if isinstance(value, dict) else value
        return {"customer": customer, "revenue": 10000000, "debt": 2000000, "cash_flow": "stable"}
