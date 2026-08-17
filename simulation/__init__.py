"""Enterprise Simulation Environment (Phase 18.13).

External system simulation services.  These are *external dependencies*: the
platform talks to them over HTTP — it never imports them.  They emulate the
representative HTTP contract of Amazon / TikTok / SAP / Salesforce / NetSuite
(provider DTOs, pagination, auth, errors, rate limiting) so that the existing
connectors exercise a real network boundary.

Simulation contract is representative, not vendor-certified.
"""
