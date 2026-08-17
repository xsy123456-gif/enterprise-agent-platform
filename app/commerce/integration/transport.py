"""HTTP transport boundary (Phase 18.13.4).

A thin, provider-agnostic HTTP client used by the connectors.  It does only
network work: GET/POST/PATCH, timeouts, headers, status and JSON decoding.  It
never understands Amazon / TikTok / ERP / CRM semantics and never maps to the
canonical domain.  Network + timeout failures surface as a retryable
``ExternalUnavailable`` so the connector retry policy can act on them.
"""

from dataclasses import dataclass

import httpx

from app.commerce.integration.errors import ExternalUnavailable


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: object  # parsed JSON (dict / list / None)
    headers: dict

    def json(self):
        return self.body


class HttpTransport:
    def __init__(self, base_url, timeout=(1.0, 5.0), client=None):
        self.base_url = (base_url or "").rstrip("/")
        if client is not None:
            self._client = client
        else:
            connect, read = timeout if isinstance(timeout, tuple) else (timeout, timeout)
            self._client = httpx.Client(
                timeout=httpx.Timeout(connect, read=read),
            )

    def request(self, method, path, params=None, headers=None,
                json_body=None) -> HttpResponse:
        url = self.base_url + path
        try:
            response = self._client.request(
                method, url, params=params, headers=headers, json=json_body,
            )
        except httpx.TimeoutException as error:
            raise ExternalUnavailable(f"timeout calling {url}") from error
        except httpx.HTTPError as error:
            raise ExternalUnavailable(f"network error calling {url}") from error
        try:
            body = response.json()
        except Exception:
            body = None
        return HttpResponse(response.status_code, body, dict(response.headers))

    def get(self, path, params=None, headers=None):
        return self.request("GET", path, params=params, headers=headers)

    def patch(self, path, params=None, headers=None, json_body=None):
        return self.request("PATCH", path, params=params, headers=headers,
                            json_body=json_body)

    def close(self):
        self._client.close()


__all__ = ["HttpTransport", "HttpResponse"]
