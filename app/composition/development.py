from .base import ApplicationContainer


def build_development(**components):
    return ApplicationContainer(environment="development", **components)
