"""Phase 18.13.3 ERP/CRM provider contract tests (SAP / Salesforce / NetSuite).

Provider basic gate: health, authentication (one success + one failure), and
one successful read per provider.
"""

import pytest
from fastapi.testclient import TestClient

from simulation.netsuite.app import build_app as netsuite_app
from simulation.salesforce.app import build_app as salesforce_app
from simulation.sap.app import build_app as sap_app

PROVIDERS = {
    "sap": (sap_app, "sim-sap-key", "/sap/v1/materials", {"plant": "PL01"}),
    "salesforce": (salesforce_app, "sim-salesforce-key",
                   "/salesforce/v1/accounts", {}),
    "netsuite": (netsuite_app, "sim-netsuite-key", "/netsuite/v1/items",
                 {"subsidiary": "SUB-001"}),
}


@pytest.mark.parametrize("name", ["sap", "salesforce", "netsuite"])
def test_health(name):
    builder, _, _, _ = PROVIDERS[name]
    response = TestClient(builder()).get("/health")
    assert response.status_code == 200
    assert response.json()["provider"] == name


@pytest.mark.parametrize("name", ["sap", "salesforce", "netsuite"])
def test_invalid_credential_401(name):
    builder, _, url, _ = PROVIDERS[name]
    response = TestClient(builder()).get(
        url, headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


@pytest.mark.parametrize("name", ["sap", "salesforce", "netsuite"])
def test_valid_credential_reads(name):
    builder, key, url, params = PROVIDERS[name]
    response = TestClient(builder()).get(
        url, params=params, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200
    assert response.json()["items"]
