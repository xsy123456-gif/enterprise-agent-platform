"""Identity provider port.

Identity Core reads identity facts only through this port; it never knows
whether data comes from local YAML, LDAP, HR API, or cloud IAM.
"""

from abc import ABC, abstractmethod

from app.identity.models.department import Department
from app.identity.models.organization import Organization
from app.identity.models.position import Position
from app.identity.models.role import Role
from app.identity.models.scope import BusinessScope
from app.identity.models.user import UserIdentity


class IdentityProviderPort(ABC):
    @abstractmethod
    def get_user(self, user_id: str) -> UserIdentity:
        raise NotImplementedError

    @abstractmethod
    def get_organization(self, organization_id: str) -> Organization:
        raise NotImplementedError

    @abstractmethod
    def get_department(self, department_id: str) -> Department:
        raise NotImplementedError

    @abstractmethod
    def get_position(self, position_id: str) -> Position:
        raise NotImplementedError

    @abstractmethod
    def get_roles(self, role_ids) -> list[Role]:
        raise NotImplementedError

    @abstractmethod
    def get_scopes(self, scope_ids) -> list[BusinessScope]:
        raise NotImplementedError
