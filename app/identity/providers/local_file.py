"""Local filesystem identity provider.

Reads enterprise identity facts from ``data/identity/*.yaml``.  This is the
first, simulated provider; replace it with LDAP/HR/cloud providers without
changing Identity Core.
"""

import os

import yaml

from app.identity.errors import (
    IdentityNotFoundError,
    IdentityProviderError,
)
from app.identity.models.department import Department
from app.identity.models.organization import Organization
from app.identity.models.position import Position
from app.identity.models.role import Role
from app.identity.models.scope import BusinessScope
from app.identity.models.user import UserIdentity
from app.identity.ports.provider import IdentityProviderPort


class LocalFileIdentityProvider(IdentityProviderPort):
    def __init__(self, data_root: str):
        if not data_root:
            raise ValueError("identity data_root is required")
        self.data_root = data_root
        self._users: dict[str, UserIdentity] = {}
        self._organizations: dict[str, Organization] = {}
        self._departments: dict[str, Department] = {}
        self._positions: dict[str, Position] = {}
        self._roles: dict[str, Role] = {}
        self._scopes: dict[str, BusinessScope] = {}
        self._load()

    def _load(self):
        try:
            self._users = {
                item["user_id"]: UserIdentity(**item)
                for item in self._read("users.yaml")["users"]
            }
            self._organizations = {
                item["organization_id"]: Organization(**item)
                for item in self._read("organizations.yaml")["organizations"]
            }
            self._departments = {
                item["department_id"]: Department(**item)
                for item in self._read("departments.yaml")["departments"]
            }
            self._positions = {
                item["position_id"]: Position(**item)
                for item in self._read("positions.yaml")["positions"]
            }
            self._roles = {
                item["role_id"]: Role(**item)
                for item in self._read("roles.yaml")["roles"]
            }
            self._scopes = {
                item["scope_id"]: BusinessScope(**item)
                for item in self._read("scopes.yaml")["scopes"]
            }
        except IdentityProviderError:
            raise
        except Exception as error:
            raise IdentityProviderError(
                f"failed to load identity data: {error}"
            ) from error

    def _read(self, name):
        path = os.path.join(self.data_root, name)
        if not os.path.isfile(path):
            raise IdentityProviderError(f"identity data file missing: {path}")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return yaml.safe_load(handle) or {}
        except Exception as error:
            raise IdentityProviderError(
                f"failed to read {path}: {error}"
            ) from error

    def get_user(self, user_id: str) -> UserIdentity:
        user = self._users.get(user_id)
        if user is None:
            raise IdentityNotFoundError(f"user not found: {user_id}")
        return user

    def get_organization(self, organization_id: str) -> Organization:
        entity = self._organizations.get(organization_id)
        if entity is None:
            raise IdentityNotFoundError(f"organization not found: {organization_id}")
        return entity

    def get_department(self, department_id: str) -> Department:
        entity = self._departments.get(department_id)
        if entity is None:
            raise IdentityNotFoundError(f"department not found: {department_id}")
        return entity

    def get_position(self, position_id: str) -> Position:
        entity = self._positions.get(position_id)
        if entity is None:
            raise IdentityNotFoundError(f"position not found: {position_id}")
        return entity

    def get_roles(self, role_ids) -> list[Role]:
        roles = []
        for role_id in role_ids:
            role = self._roles.get(role_id)
            if role is None:
                raise IdentityNotFoundError(f"role not found: {role_id}")
            roles.append(role)
        return roles

    def get_scopes(self, scope_ids) -> list[BusinessScope]:
        scopes = []
        for scope_id in scope_ids:
            scope = self._scopes.get(scope_id)
            if scope is None:
                raise IdentityNotFoundError(f"scope not found: {scope_id}")
            scopes.append(scope)
        return scopes

    def health(self):
        return {
            "name": "identity.provider",
            "healthy": True,
            "users": len(self._users),
            "organizations": len(self._organizations),
            "departments": len(self._departments),
        }
