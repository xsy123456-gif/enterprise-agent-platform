from .base import ApplicationContainer


def build_testing(**components):
    return ApplicationContainer(environment="testing", **components)
