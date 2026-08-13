"""Haystack adapter exceptions.

Backend failures are mapped to platform ``Knowledge*Error`` at the adapter
boundary.  These exceptions are only for adapter-internal misconfiguration.
"""


class HaystackAdapterError(RuntimeError):
    """Base error for the Haystack knowledge adapter."""


class HaystackConfigError(HaystackAdapterError):
    """The adapter was built with an invalid configuration."""
