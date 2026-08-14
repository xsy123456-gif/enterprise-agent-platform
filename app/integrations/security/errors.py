"""Execution security integration errors."""


class SecurityIntegrationError(Exception):
    """Base error for the execution security integration layer."""


class TrustedPrincipalResolutionError(SecurityIntegrationError):
    """The trusted principal could not be resolved into a subject (fail-closed)."""


class SecurityContextError(SecurityIntegrationError):
    """The execution security context is missing or invalid."""
