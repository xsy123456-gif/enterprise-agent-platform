"""Salesforce CRM simulation DTOs (Phase 18.13).

Salesforce-like field naming (``Id``, ``Name``, ``Industry``, ``AnnualRevenue``,
``StageName``, ``CaseNumber``).  CRM-only semantics — no commerce orders here.
"""

ORG_ID = "00D000000000001"

ACCOUNTS = [
    {"Id": "001000001", "Name": "Tesla", "Industry": "Automotive",
     "AnnualRevenue": 50000000.0, "Type": "Customer"},
    {"Id": "001000002", "Name": "Panasonic", "Industry": "Electronics",
     "AnnualRevenue": 30000000.0, "Type": "Prospect"},
]

CONTACTS = [
    {"Id": "003000001", "AccountId": "001000001", "FirstName": "Elon",
     "LastName": "Musk", "Email": "elon@example.com"},
    {"Id": "003000002", "AccountId": "001000002", "FirstName": "Kazuo",
     "LastName": "Tanaka", "Email": "kazuo@example.com"},
]

OPPORTUNITIES = [
    {"Id": "006000001", "AccountId": "001000001", "Name": "Fleet Deal",
     "StageName": "Negotiation", "Amount": 200000.0, "CloseDate": "2026-09-01"},
    {"Id": "006000002", "AccountId": "001000002", "Name": "Component Renewal",
     "StageName": "Closed Won", "Amount": 50000.0, "CloseDate": "2026-08-15"},
]

CASES = [
    {"Id": "500000001", "AccountId": "001000001", "CaseNumber": "00001001",
     "Status": "Open", "Priority": "High", "Subject": "Battery performance"},
    {"Id": "500000002", "AccountId": "001000002", "CaseNumber": "00001002",
     "Status": "Closed", "Priority": "Low", "Subject": "Billing question"},
]
