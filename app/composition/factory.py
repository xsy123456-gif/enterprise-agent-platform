import os

from .development import build_development
from .production import build_production
from .testing import build_testing


def create_application(environment=None, **components):
    environment = (environment or os.getenv("APP_ENV", "development")).lower()
    builders = {
        "development": build_development,
        "testing": build_testing,
        "production": build_production,
    }
    try:
        return builders[environment](**components)
    except KeyError as error:
        raise ValueError(
            f"Unsupported APP_ENV {environment!r}; expected development, testing, or production"
        ) from error
