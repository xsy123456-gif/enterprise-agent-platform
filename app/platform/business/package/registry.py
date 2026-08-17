"""Package registry + lifecycle (Phase 16.1)."""

from app.core.versioning import VersionedRegistry
from app.platform.business.errors import PackageNotPublishedError
from app.platform.business.package.domain import (
    PACKAGE_DEPRECATED,
    PACKAGE_DRAFT,
    PACKAGE_PUBLISHED,
    PACKAGE_VALIDATED,
    AgentPackage,
)


class PackageRegistry(VersionedRegistry):

    def __init__(self):
        super().__init__("package")
        self._status = {}

    def register(self, package: AgentPackage):
        super().register(package.package_id, package.version, package)
        self._status[(package.package_id, package.version)] = PACKAGE_DRAFT
        return package

    def validate(self, package_id, version=None):
        from dataclasses import replace
        version = self._resolve(package_id, version)
        if not self._items[(package_id, version)].agents:
            from app.platform.business.errors import PackageValidationError
            raise PackageValidationError(
                f"package {package_id!r} declares no agents"
            )
        self._items[(package_id, version)] = replace(
            self._items[(package_id, version)], status=PACKAGE_VALIDATED)
        self._status[(package_id, version)] = PACKAGE_VALIDATED
        return self._items[(package_id, version)]

    def publish(self, package_id, version=None):
        from dataclasses import replace
        version = self._resolve(package_id, version)
        self._items[(package_id, version)] = replace(
            self._items[(package_id, version)], status=PACKAGE_PUBLISHED)
        self._status[(package_id, version)] = PACKAGE_PUBLISHED
        self._active[package_id] = version
        return self._items[(package_id, version)]

    def deprecate(self, package_id, version=None):
        version = self._resolve(package_id, version)
        self._status[(package_id, version)] = PACKAGE_DEPRECATED

    def status(self, package_id, version=None):
        return self._status[self._resolve(package_id, version)]

    def get_published(self, package_id, version=None):
        version = self._resolve(package_id, version)
        if self._status[(package_id, version)] != PACKAGE_PUBLISHED:
            raise PackageNotPublishedError(
                f"package {package_id!r}@{version} is not PUBLISHED"
            )
        return self._items[(package_id, version)]

    def get(self, package_id, version=None):
        return super().get(package_id, version)

    def _resolve(self, package_id, version):
        if version is not None:
            if (package_id, version) not in self._items:
                from app.core.errors import UnknownDefinitionVersionError
                raise UnknownDefinitionVersionError(
                    f"package {package_id!r} has no version {version!r}"
                )
            return version
        active = self._active.get(package_id)
        if active is not None:
            return active
        versions = self.versions(package_id)
        if not versions:
            from app.core.errors import UnknownDefinitionError
            raise UnknownDefinitionError(f"package {package_id!r} is not registered")
        return versions[0]


__all__ = ["PackageRegistry"]
