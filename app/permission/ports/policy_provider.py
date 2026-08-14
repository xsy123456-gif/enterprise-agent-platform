"""Policy provider port — where policies come from."""

from abc import ABC, abstractmethod

from app.permission.models.policy import PermissionPolicy


class PolicyProviderPort(ABC):
    @abstractmethod
    def load_policies(self) -> list[PermissionPolicy]:
        raise NotImplementedError
