class LifecycleTransitionError(ValueError):
    pass


class LifecyclePolicy:
    TRANSITIONS = {
        "draft": {"validating"},
        "validating": {"reviewing"},
        "reviewing": {"approved"},
        "approved": {"active"},
        "active": {"suspended", "deprecated"},
        "deprecated": {"archived"},
        "suspended": set(),
        "archived": set(),
    }

    def validate(self, current, target):
        if target not in self.TRANSITIONS:
            raise LifecycleTransitionError(f"Unknown lifecycle status: {target}")
        if target not in self.TRANSITIONS.get(current, set()):
            raise LifecycleTransitionError(
                f"Invalid lifecycle transition: {current} -> {target}"
            )
