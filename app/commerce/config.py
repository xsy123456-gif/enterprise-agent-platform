"""Commerce data-layer configuration.

Production storage uses PostgreSQL.  The URL is provided by the environment;
there is no embedded default so a misconfigured environment fails fast rather
than silently writing to the wrong database.
"""

from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class CommerceConfig:
    database_url: str | None = None
    initialize: bool = False
    canonical_schema_version: str = "1.0"

    @classmethod
    def from_environment(cls, environ=None):
        env = dict(os.environ if environ is None else environ)
        initialize = env.get("COMMERCE_DATABASE_INITIALIZE", "").lower() in {
            "1", "true", "yes",
        }
        return cls(
            database_url=env.get("COMMERCE_DATABASE_URL"),
            initialize=initialize,
            canonical_schema_version=env.get(
                "COMMERCE_CANONICAL_SCHEMA_VERSION", "1.0"
            ),
        )
