from .base import ApplicationContainer


def build_production(**components):
    """Build the production boundary without opening external connections."""
    return ApplicationContainer(environment="production", **components)
