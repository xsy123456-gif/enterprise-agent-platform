"""HTTP server entrypoint (Phase 18.12).

Deployment composition: build the platform -> build auth provider ->
create_http_app.  ``create_app`` is the uvicorn factory (--factory).
"""

import os

from app.api.auth import DevAuthenticationProvider, TestAuthenticationProvider
from app.api.config import api_config_for
from app.api.factory import create_http_app


def build_http_application(environment=None, application=None, **overrides):
    environment = (environment or os.getenv("APP_ENV", "testing")).lower()
    if application is None:
        from app.composition.enterprise import build_enterprise_application
        application = build_enterprise_application(environment, **overrides)
    application.start()
    config = api_config_for(environment)
    if environment == "development":
        auth = DevAuthenticationProvider()
    else:
        auth = TestAuthenticationProvider()
    return create_http_app(application, auth, config)


def create_app():
    return build_http_application()


__all__ = ["build_http_application", "create_app"]
