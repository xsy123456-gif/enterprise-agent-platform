from app.governance.policy.models import PolicyDecision, PolicyRequest


class PolicyDecisionEngine:
    def __init__(self, repository, default_decision="deny"):
        self.repository = repository
        self.default_decision = default_decision

    def register(self, policy):
        self.repository.add(policy)
        return policy

    def check(self, request, policy_id=None):
        if isinstance(request, dict):
            request = PolicyRequest(**request)
        policies = []
        if policy_id is not None:
            policy = self.repository.get(policy_id)
            if policy is not None:
                policies.append(policy)
        else:
            policies = list(getattr(self.repository, "_policies", {}).values())
        for policy in policies:
            for rule in policy.rules:
                if self._matches(rule.subject, request.role, request.user_id) and \
                   self._matches(rule.action, request.action) and \
                   self._matches(rule.resource, request.agent_id, request.resource):
                    effect = rule.effect.lower()
                    return PolicyDecision(effect, f"Matched policy rule in {policy.policy_id}")
        return PolicyDecision(self.default_decision, "No applicable governance policy rule")

    @staticmethod
    def _matches(value, *candidates):
        return value == "*" or value in candidates
