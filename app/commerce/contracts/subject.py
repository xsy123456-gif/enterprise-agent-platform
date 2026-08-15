"""Subject reference contract.

A unified ``SubjectRef`` for every commerce subject.  Internal diagnostic work
accepts canonical ids only; external platform ids must be resolved through the
identity map before a ``SubjectRef`` is created.
"""

from dataclasses import dataclass

from app.commerce.contracts.errors import CommerceValidationError

SUBJECT_STORE = "STORE"
SUBJECT_PRODUCT = "PRODUCT"
SUBJECT_SKU = "SKU"
SUBJECT_LISTING = "LISTING"
SUBJECT_LISTING_ITEM = "LISTING_ITEM"
SUBJECT_CAMPAIGN = "CAMPAIGN"
SUBJECT_AD_GROUP = "AD_GROUP"
SUBJECT_AD = "AD"
SUBJECT_KEYWORD = "KEYWORD"
SUBJECT_SEARCH_TERM = "SEARCH_TERM"

SUBJECT_TYPES = frozenset({
    SUBJECT_STORE,
    SUBJECT_PRODUCT,
    SUBJECT_SKU,
    SUBJECT_LISTING,
    SUBJECT_LISTING_ITEM,
    SUBJECT_CAMPAIGN,
    SUBJECT_AD_GROUP,
    SUBJECT_AD,
    SUBJECT_KEYWORD,
    SUBJECT_SEARCH_TERM,
})


@dataclass(frozen=True)
class SubjectRef:
    type: str
    id: str

    def __post_init__(self):
        if self.type not in SUBJECT_TYPES:
            raise CommerceValidationError(f"unknown subject type: {self.type}")
        if not self.id:
            raise CommerceValidationError("subject id must not be empty")

    def to_dict(self) -> dict:
        return {"type": self.type, "id": self.id}

    @classmethod
    def from_dict(cls, data: dict) -> "SubjectRef":
        return cls(type=data["type"], id=data["id"])

    def key(self) -> str:
        return f"{self.type}:{self.id}"


__all__ = [
    "SubjectRef",
    "SUBJECT_TYPES",
    "SUBJECT_STORE",
    "SUBJECT_PRODUCT",
    "SUBJECT_SKU",
    "SUBJECT_LISTING",
    "SUBJECT_LISTING_ITEM",
    "SUBJECT_CAMPAIGN",
    "SUBJECT_AD_GROUP",
    "SUBJECT_AD",
    "SUBJECT_KEYWORD",
    "SUBJECT_SEARCH_TERM",
]
