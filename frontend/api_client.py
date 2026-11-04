"""
InfraSight API Client for Streamlit Frontend (Phase 5).
Thin client over FastAPI backend.
Handles all HTTP communication, error encapsulation, and authentication.
Contains zero business logic or authorization.
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple
import requests


class APIClientError(Exception):
    """Base exception for API communication errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, detail: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail or message


class APIConnectionError(APIClientError):
    """Backend unreachable or network connection failure."""
    pass


class InfraSightAPIClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or os.getenv("BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.timeout = 30

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _handle_response(self, resp: requests.Response) -> Dict[str, Any]:
        try:
            data = resp.json()
        except Exception:
            data = {"detail": resp.text}

        if resp.status_code >= 400:
            detail = data.get("detail", f"HTTP {resp.status_code}: {resp.text}")
            raise APIClientError(
                message=f"API Error ({resp.status_code}): {detail}",
                status_code=resp.status_code,
                detail=detail,
            )
        return data

    def health_check(self) -> Dict[str, Any]:
        """Checks if backend service is available."""
        try:
            resp = requests.get(self._url("/health"), timeout=1.5)
            return self._handle_response(resp)
        except (requests.exceptions.RequestException, APIClientError) as e:
            raise APIConnectionError(
                f"Cannot connect to InfraSight backend at {self.base_url}. Ensure server is running."
            ) from e

    def list_scenarios(self) -> List[Dict[str, Any]]:
        """Fetches sanitized synthetic scenario definitions."""
        try:
            resp = requests.get(self._url("/scenarios"), timeout=self.timeout)
            return self._handle_response(resp)
        except requests.exceptions.RequestException as e:
            raise APIConnectionError(f"Failed to fetch scenario list: {e}") from e

    def get_usage_summary(self) -> Dict[str, Any]:
        """Fetches cumulative token and cost summary across all runs."""
        try:
            resp = requests.get(self._url("/usage/summary"), timeout=self.timeout)
            return self._handle_response(resp)
        except requests.exceptions.RequestException as e:
            raise APIConnectionError(f"Failed to fetch usage summary: {e}") from e

    def create_incident(
        self,
        description: str,
        image_files: Optional[List[Tuple[str, bytes, str]]] = None,
        image_paths: Optional[List[str]] = None,
        mode: str = "replay",
        live_password: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a new incident record.
        image_files is a list of (filename, bytes_data, content_type)
        image_paths is a list of pre-existing image file paths
        """
        files = []
        if image_files:
            for fname, bdata, ctype in image_files:
                files.append(("images", (fname, bdata, ctype)))

        data = {"description": description, "mode": mode}
        if live_password:
            data["live_password"] = live_password
        if image_paths:
            data["image_paths"] = json.dumps(image_paths)

        headers = {}
        if live_password:
            headers["X-Live-Password"] = live_password
        if session_id:
            headers["X-Session-ID"] = session_id

        try:
            resp = requests.post(
                self._url("/incidents"),
                data=data,
                files=files if files else None,
                headers=headers if headers else None,
                timeout=self.timeout,
            )
            return self._handle_response(resp)
        except requests.exceptions.RequestException as e:
            raise APIConnectionError(f"Failed to submit incident: {e}") from e

    def start_investigation(
        self,
        incident_id: str,
        sync: bool = False,
        mode: str = "replay",
        live_password: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Starts investigation worker."""
        headers = {}
        if live_password:
            headers["X-Live-Password"] = live_password
        if session_id:
            headers["X-Session-ID"] = session_id

        params: Dict[str, Any] = {"sync": sync, "mode": mode}
        if live_password:
            params["live_password"] = live_password

        try:
            resp = requests.post(
                self._url(f"/incidents/{incident_id}/investigate"),
                params=params,
                headers=headers if headers else None,
                timeout=120 if sync else self.timeout,
            )
            return self._handle_response(resp)
        except requests.exceptions.RequestException as e:
            raise APIConnectionError(f"Failed to start investigation: {e}") from e

    def get_incident(self, incident_id: str) -> Dict[str, Any]:
        """Fetches complete incident state, timeline, and pending actions."""
        try:
            resp = requests.get(self._url(f"/incidents/{incident_id}"), timeout=self.timeout)
            return self._handle_response(resp)
        except requests.exceptions.RequestException as e:
            raise APIConnectionError(f"Failed to fetch incident '{incident_id}': {e}") from e

    def get_incident_report(self, incident_id: str) -> str:
        """Fetches full Markdown audit report."""
        try:
            resp = requests.get(self._url(f"/incidents/{incident_id}/report"), timeout=self.timeout)
            data = self._handle_response(resp)
            return data.get("report", "")
        except requests.exceptions.RequestException as e:
            raise APIConnectionError(f"Failed to fetch incident report: {e}") from e

    def approve_action(
        self,
        action_id: str,
        approver_token: Optional[str] = None,
        decided_by: str = "supervisor@local",
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Approves pending Class B remediation action.
        Returns (success_bool, message_str, details_dict).
        """
        headers = {}
        token = approver_token or os.getenv("APPROVER_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            resp = requests.post(
                self._url(f"/actions/{action_id}/approve"),
                json={"decided_by": decided_by},
                headers=headers,
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                return True, "Action approved and executed successfully in simulation.", data
            
            # Handle specific error status codes cleanly
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            detail = data.get("detail", resp.text)
            if resp.status_code == 401:
                return False, f"Authentication Failed (401): {detail}", data
            if resp.status_code == 409:
                return False, f"Action Already Decided (409): {detail}", data
            if resp.status_code in [410, 422]:
                return False, f"Action Expired or Invalid ({resp.status_code}): {detail}", data
            return False, f"Approval Failed ({resp.status_code}): {detail}", data
        except requests.exceptions.RequestException as e:
            return False, f"Network communication error during approval: {e}", {}

    def reject_action(
        self,
        action_id: str,
        approver_token: Optional[str] = None,
        decided_by: str = "supervisor@local",
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Rejects pending Class B remediation action.
        Returns (success_bool, message_str, details_dict).
        """
        headers = {}
        token = approver_token or os.getenv("APPROVER_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            resp = requests.post(
                self._url(f"/actions/{action_id}/reject"),
                json={"decided_by": decided_by},
                headers=headers,
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                return True, "Action rejected. Hardware remains unchanged.", data
            
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            detail = data.get("detail", resp.text)
            if resp.status_code == 401:
                return False, f"Authentication Failed (401): {detail}", data
            if resp.status_code == 409:
                return False, f"Action Already Decided (409): {detail}", data
            if resp.status_code in [410, 422]:
                return False, f"Action Expired or Invalid ({resp.status_code}): {detail}", data
            return False, f"Rejection Failed ({resp.status_code}): {detail}", data
        except requests.exceptions.RequestException as e:
            return False, f"Network communication error during rejection: {e}", {}

    def run_policy_stress_test(self) -> Dict[str, Any]:
        """
        Triggers the scripted adversarial policy stress test on the backend.
        Returns the incident result with authentic audit events and outcomes.
        """
        resp = requests.post(self._url("/policy/stress-test"), timeout=self.timeout)
        return self._handle_response(resp)
