"""Business scope — tenant-owned enterprise entity.

Objective business attribution (stores / regions / channels / brands /
products / business units).  It is NOT authorization: it does not decide what
a person may access, only which business areas they belong to.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BusinessScope:
    scope_id: str
    tenant_id: str
    stores: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    channels: tuple[str, ...] = ()
    brands: tuple[str, ...] = ()
    products: tuple[str, ...] = ()
    business_units: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "stores", tuple(self.stores or ()))
        object.__setattr__(self, "regions", tuple(self.regions or ()))
        object.__setattr__(self, "channels", tuple(self.channels or ()))
        object.__setattr__(self, "brands", tuple(self.brands or ()))
        object.__setattr__(self, "products", tuple(self.products or ()))
        object.__setattr__(self, "business_units", tuple(self.business_units or ()))

    def to_dict(self):
        return {
            "scope_id": self.scope_id,
            "tenant_id": self.tenant_id,
            "stores": sorted(self.stores),
            "regions": sorted(self.regions),
            "channels": sorted(self.channels),
            "brands": sorted(self.brands),
            "products": sorted(self.products),
            "business_units": sorted(self.business_units),
        }
