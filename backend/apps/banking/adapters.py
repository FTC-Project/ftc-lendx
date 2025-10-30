import os
from typing import Any, Dict, List, Optional, cast
from urllib.parse import urlencode

import requests


class AISClient:
    """
    A client for the Open Banking AIS Sandbox API, refactored to the spec.
    """

    def __init__(self):
        self.base_url = os.environ.get(
            "OPENBANK_BASE_URL", "https://open-banking-ais.onrender.com"
        )
        self.client_id = os.environ.get("CLIENT_ID", "tp_demo")
        self.client_secret = os.environ.get("CLIENT_SECRET", "s3cr3t")
        self.timeout = 15
        # Use a session for connection pooling
        self.session = requests.Session()

    def _auth_bearer_header(self, token: str) -> dict[str, str]:
        """Creates a Bearer token authorization header."""
        return {"Authorization": f"Bearer {token}"}

    def _handle_error(self, response: requests.Response, prefix: str) -> None:
        """Checks for HTTP errors and raises a descriptive RuntimeError."""
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            detail = e.response.text
            try:
                # Try to parse a structured error (like HTTPValidationError)
                error_json = e.response.json()
                detail = error_json.get("detail", detail)
            except requests.JSONDecodeError:
                pass  # Stick with the raw text
            raise RuntimeError(
                f"{prefix} failed ({e.response.status_code}): {detail}"
            ) from e

    def _clean_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Removes None values from a params dict."""
        return {k: v for k, v in params.items() if v is not None}

    def post_token(self, consent_id: Optional[str] = None) -> dict[str, Any]:
        """
        POST /connect/mtls/token

        Gets a client_credentials token.
        Spec requires application/x-www-form-urlencoded with client credentials
        in the body.
        """
        scope = "ais"
        if consent_id is not None:
            scope = "accounts.read balances.read transactions.read"
        url = f"{self.base_url}/connect/mtls/token"
        form_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": scope,
        }
        if consent_id is not None:
            form_data["consent_id"] = consent_id

        r = self.session.post(
            url,
            data=form_data,
            timeout=self.timeout,
        )

        self._handle_error(r, "Token request")
        return cast(dict[str, Any], r.json())

    def refresh_token(
        self, refresh_token: str, consent_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        POST /connect/mtls/token with refresh_token grant

        Refreshes an access token using a refresh token.
        """
        url = f"{self.base_url}/connect/mtls/token"
        form_data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
        }
        if consent_id is not None:
            form_data["consent_id"] = consent_id

        r = self.session.post(
            url,
            data=form_data,
            timeout=self.timeout,
        )

        self._handle_error(r, "Token refresh")
        return cast(dict[str, Any], r.json())

    def post_consent(self, access_token: str, permissions: list[str]) -> dict[str, Any]:
        """
        POST /account-access-consents

        Creates a new account access consent.
        """
        url = f"{self.base_url}/account-access-consents"
        payload = {
            "permissions": permissions,
            "expirationDateTime": "2099-01-01T00:00:00Z",  # Hardcoded far-future expiry
        }
        headers = self._auth_bearer_header(access_token)

        r = self.session.post(
            url,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )

        self._handle_error(r, "Consent creation")
        return cast(dict[str, Any], r.json())

    def get_consent(self, access_token: str, consent_id: str) -> dict[str, Any]:
        """
        GET /account-access-consents/{ConsentId}

        Fetches the status and details of a specific consent.
        """
        url = f"{self.base_url}/account-access-consents/{consent_id}"
        headers = self._auth_bearer_header(access_token)

        r = self.session.get(
            url,
            headers=headers,
            timeout=self.timeout,
        )

        self._handle_error(r, "Get consent status")
        return cast(dict[str, Any], r.json())

    def get_psu_ui_url(self, consent_id: str, psu_id: str, redirect_uri: str) -> str:
        """
        Constructs the URL for:
        GET /psu/authorize/ui

        This is the URL the end-user (PSU) should be redirected to.
        """
        params = {
            "consentId": consent_id,
            "psu_id": psu_id,
            "redirect_uri": redirect_uri,
        }
        return f"{self.base_url}/psu/authorize/ui?{urlencode(params)}"

    def get_psu_reject_url(self, consent_id: str, redirect_uri: str) -> str:
        """
        Constructs the URL for:
        GET /psu/authorize/reject

        This URL simulates the user rejecting the consent.
        """
        params = {"consentId": consent_id, "redirect_uri": redirect_uri}
        return f"{self.base_url}/psu/authorize/reject?{urlencode(params)}"

    def psu_authorize(
        self, consent_id: str, psu_id: str, redirect_uri: Optional[str] = None
    ) -> dict[str, Any]:
        """
        POST /psu/authorize

        Simulates the user approving the consent (e.g., after the UI redirect).
        The spec does not define a security requirement (e.g., Bearer token)
        for this endpoint, so no Authorization header is sent.
        """
        url = f"{self.base_url}/psu/authorize"

        # The spec indicates 'selected_accounts' is not required
        form_data = {
            "consentId": consent_id,
            "psu_id": psu_id,
            "redirect_uri": redirect_uri,
        }

        r = self.session.post(
            url,
            data=self._clean_params(form_data),
            timeout=self.timeout,
        )

        self._handle_error(r, "PSU authorization simulation")
        # This endpoint may return an empty body on success
        return r.json() if r.text else {}

    def list_accounts(
        self,
        access_token: str,
        limit: Optional[int] = None,
        after: Optional[str] = None,
        consent_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        GET /accounts

        Lists all accounts authorized by the consent.
        """
        url = f"{self.base_url}/accounts"
        headers = self._auth_bearer_header(access_token)

        params = {"limit": limit, "after": after}

        if consent_id is not None:
            params["consentId"] = consent_id

        r = self.session.get(
            url,
            headers=headers,
            params=self._clean_params(params),
            timeout=self.timeout,
        )

        self._handle_error(r, "List accounts")
        return cast(dict[str, Any], r.json())

    def get_account(self, access_token: str, account_id: str) -> dict[str, Any]:
        """
        GET /accounts/{accountId}

        Gets details for a specific account.
        """
        url = f"{self.base_url}/accounts/{account_id}"
        headers = self._auth_bearer_header(access_token)

        r = self.session.get(
            url,
            headers=headers,
            timeout=self.timeout,
        )

        self._handle_error(r, "Get account")
        return cast(dict[str, Any], r.json())

    def get_balances(self, access_token: str, account_id: str) -> dict[str, Any]:
        """
        GET /accounts/{accountId}/balances

        Gets balances for a specific account.
        """
        url = f"{self.base_url}/accounts/{account_id}/balances"
        headers = self._auth_bearer_header(access_token)

        r = self.session.get(
            url,
            headers=headers,
            timeout=self.timeout,
        )

        self._handle_error(r, "Get balances")
        return cast(dict[str, Any], r.json())

    def list_balances(self, access_token: str) -> list[dict[str, Any]]:
        """
        GET /balances

        Lists balances for all authorized accounts.
        """
        url = f"{self.base_url}/balances"
        headers = self._auth_bearer_header(access_token)

        r = self.session.get(
            url,
            headers=headers,
            timeout=self.timeout,
        )

        self._handle_error(r, "List balances")
        return cast(list[dict[str, Any]], r.json())

    def list_beneficiaries_by_account(
        self, access_token: str, account_id: str
    ) -> list[dict[str, Any]]:
        """
        GET /accounts/{accountId}/beneficiaries

        Lists beneficiaries for a specific account.
        """
        url = f"{self.base_url}/accounts/{account_id}/beneficiaries"
        headers = self._auth_bearer_header(access_token)

        r = self.session.get(
            url,
            headers=headers,
            timeout=self.timeout,
        )

        self._handle_error(r, "List beneficiaries by account")
        return cast(list[dict[str, Any]], r.json())

    def list_beneficiaries(self, access_token: str) -> list[dict[str, Any]]:
        """
        GET /beneficiaries

        Lists beneficiaries for all authorized accounts.
        """
        url = f"{self.base_url}/beneficiaries"
        headers = self._auth_bearer_header(access_token)

        r = self.session.get(
            url,
            headers=headers,
            timeout=self.timeout,
        )

        self._handle_error(r, "List beneficiaries")
        return cast(list[dict[str, Any]], r.json())

    def list_transactions_by_account(
        self,
        access_token: str,
        account_id: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: Optional[int] = None,
        after: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        GET /accounts/{accountId}/transactions

        Lists transactions for a specific account.
        """
        url = f"{self.base_url}/accounts/{account_id}/transactions"
        headers = self._auth_bearer_header(access_token)
        params = {
            "fromDate": from_date,
            "toDate": to_date,
            "limit": limit,
            "after": after,
        }

        r = self.session.get(
            url,
            headers=headers,
            params=self._clean_params(params),
            timeout=self.timeout,
        )

        self._handle_error(r, "Get transactions by account")
        return cast(dict[str, Any], r.json())

    def list_transactions_all(
        self,
        access_token: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: Optional[int] = None,
        after: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        GET /transactions

        Lists transactions for all authorized accounts.
        """
        url = f"{self.base_url}/transactions"
        headers = self._auth_bearer_header(access_token)
        params = {
            "fromDate": from_date,
            "toDate": to_date,
            "limit": limit,
            "after": after,
        }

        r = self.session.get(
            url,
            headers=headers,
            params=self._clean_params(params),
            timeout=self.timeout,
        )

        self._handle_error(r, "List all transactions")
        return cast(dict[str, Any], r.json())
