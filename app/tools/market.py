from app.tools.base import BaseTool


class MarketTool(BaseTool):
    name = "market_query"
    description = "查询客户所在市场信息"
    input_schema = {
        "type": "object",
        "properties": {"customer": {"type": "string", "description": "客户标识，例如 customer_A"}},
        "required": ["customer"],
    }

    def validate_input(self, value):
        if isinstance(value, dict):
            value = value.get("industry") or value.get("customer")
        return isinstance(value, str) and bool(value.strip())

    def execute(self, value):
        subject = value.get("industry") or value.get("customer") if isinstance(value, dict) else value
        return {"subject": subject, "growth": "high", "competition": "medium", "trend": "expanding"}
