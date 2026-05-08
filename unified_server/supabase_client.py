from __future__ import annotations

from typing import Any

import requests

from unified_server.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL


class SupabaseConfigError(Exception):
    pass


class SupabaseRequestError(Exception):
    pass


class SupabaseRestClient:
    def __init__(self, base_url: str | None = None, service_role_key: str | None = None) -> None:
        self.base_url = (base_url or SUPABASE_URL).rstrip("/")
        self.service_role_key = service_role_key or SUPABASE_SERVICE_ROLE_KEY
        if not self.base_url or not self.service_role_key:
            raise SupabaseConfigError("Supabase URL/service role key is not configured.")

    def select(self, table: str, *, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        response = self._request("GET", f"/rest/v1/{table}", params=query)
        return response.json()

    def insert(self, table: str, payload: dict[str, Any] | list[dict[str, Any]], *, returning: str = "representation") -> list[dict[str, Any]]:
        headers = {"Prefer": f"return={returning}"}
        response = self._request("POST", f"/rest/v1/{table}", json=payload, headers=headers)
        return response.json() if response.content else []

    def update(self, table: str, payload: dict[str, Any], *, query: dict[str, Any], returning: str = "representation") -> list[dict[str, Any]]:
        headers = {"Prefer": f"return={returning}"}
        response = self._request("PATCH", f"/rest/v1/{table}", params=query, json=payload, headers=headers)
        return response.json() if response.content else []

    def delete(self, table: str, *, query: dict[str, Any], returning: str = "representation") -> list[dict[str, Any]]:
        headers = {"Prefer": f"return={returning}"}
        response = self._request("DELETE", f"/rest/v1/{table}", params=query, headers=headers)
        return response.json() if response.content else []

    def rpc(self, function_name: str, payload: dict[str, Any]) -> Any:
        response = self._request("POST", f"/rest/v1/rpc/{function_name}", json=payload)
        return response.json() if response.content else None

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        url = f"{self.base_url}{path}"
        merged_headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
        }
        if headers:
            merged_headers.update(headers)
        response = requests.request(method, url, params=params, json=json, headers=merged_headers, timeout=60)
        if response.status_code >= 400:
            raise SupabaseRequestError(f"Supabase error ({response.status_code}): {response.text}")
        return response
