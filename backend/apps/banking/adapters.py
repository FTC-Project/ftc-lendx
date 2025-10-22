import base64
import os
from typing import Dict, List

import requests


class AISClient:
    """A client for the mock Open Banking AIS API."""

    def __init__(self):
        self.base_url = os.environ.get(
            "OPENBANK_BASE_URL", "https://open-banking-ais.onrender.com"
        )
        self.client_id = os.environ.get("CLIENT_ID", "tp_demo")
        self.client_secret = os.environ.get("CLIENT_SECRET", "s3cr3t")
        self.x_client_cert = os.environ.get("X_CLIENT_CERT", "DEMO-CLIENT-CERT")
        self.timeout = 15

    def _basic_auth_header(self) -> Dict[str, str]:
        auth_str = f"{self.client_id}:{self.client_secret}"
        basic = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {basic}"}

    def _auth_bearer_header(self, token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _handle_error(self, response: requests.Response, prefix: str) -> None:
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            detail = getattr(e.response, "text", "")
            raise RuntimeError(
                f"{prefix} failed ({e.response.status_code}): {detail}"
            ) from e

    def post_token(self) -> Dict:
        """POST /connect/mtls/token"""
        headers = self._basic_auth_header()
        headers["X-Client-Cert"] = self.x_client_cert
        body = {"grant_type": "client_credentials", "scope": "ais"}

        r = requests.post(
            f"{self.base_url}/connect/mtls/token",
            headers=headers,
            json=body,
            timeout=self.timeout,
        )
        if r.status_code == 415:  # Unsupported Media Type, fallback to form data
            r = requests.post(
                f"{self.base_url}/connect/mtls/token",
                headers=headers,
                data=body,
                timeout=self.timeout,
            )

        self._handle_error(r, "Token request")
        return r.json()

    def post_consent(self, access_token: str, permissions: List[str]) -> Dict:
        """POST /account-access-consents"""
        payload = {
            "permissions": permissions,
            "expirationDateTime": "2099-01-01T00:00:00Z",
        }
        r = requests.post(
            f"{self.base_url}/account-access-consents",
            json=payload,
            headers=self._auth_bearer_header(access_token),
            timeout=self.timeout,
        )
        self._handle_error(r, "Consent creation")
        return r.json()

    def get_consent(self, access_token: str, consent_id: str) -> Dict:
        """GET /account-access-consents/{consent_id}"""
        r = requests.get(
            f"{self.base_url}/account-access-consents/{consent_id}",
            headers=self._auth_bearer_header(access_token),
            timeout=self.timeout,
        )
        self._handle_error(r, "Get consent status")
        return r.json()

    def psu_authorize(
        self, access_token: str, consent_id: str, redirect_uri: str
    ) -> Dict:
        """POST /psu/authorize (simulates user approval)"""
        form = {"consentId": consent_id, "redirect_uri": redirect_uri}
        r = requests.post(
            f"{self.base_url}/psu/authorize",
            data=form,
            headers=self._auth_bearer_header(access_token),
            timeout=self.timeout,
        )
        self._handle_error(r, "PSU authorization simulation")
        return r.json() if r.text else {}

    def list_accounts(self, access_token: str) -> List[Dict]:
        """GET /accounts"""
        r = requests.get(
            f"{self.base_url}/accounts",
            headers=self._auth_bearer_header(access_token),
            timeout=self.timeout,
        )
        self._handle_error(r, "List accounts")
        data = r.json() or {}
        return data.get("data", []) if isinstance(data, dict) else data

    def get_transactions(self, access_token: str, account_id: str) -> List[Dict]:
        """GET /accounts/{account_id}/transactions"""
        r = requests.get(
            f"{self.base_url}/accounts/{account_id}/transactions",
            headers=self._auth_bearer_header(access_token),
            timeout=self.timeout,
        )
        self._handle_error(r, "Get transactions")
        data = r.json() or {}
        return data.get("data", []) if isinstance(data, dict) else data

    def get_psu_ui_url(self, consent_id: str, redirect_uri: str) -> str:
        """Constructs the PSU authorization UI URL."""
        return f"{self.base_url}/psu/authorize/ui?consentId={consent_id}&redirect_uri={redirect_uri}"
