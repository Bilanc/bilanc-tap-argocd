"""Argo CD REST API client."""
import backoff
import requests
import urllib3
from singer import get_logger

LOGGER = get_logger()


class ArgoCDError(Exception):
    pass


class RetryableError(ArgoCDError):
    pass


def split_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    return [item for item in value.replace(",", " ").split() if item]


class Client:
    def __init__(self, config):
        self.base_url = config["base_url"].rstrip("/")
        self.start_date = config["start_date"]
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {config['token']}", "Accept": "application/json"})
        self.session.verify = str(config.get("verify_ssl", True)).lower() != "false"
        if not self.session.verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.timeout = int(config.get("request_timeout", 300))
        self.projects = split_list(config.get("projects"))
        self.selector = config.get("selector")
        self._applications = None

    @backoff.on_exception(
        backoff.expo,
        (RetryableError, requests.ConnectionError, requests.Timeout),
        max_tries=5,
        factor=2,
    )
    def get(self, path, params=None):
        response = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        if response.status_code == 429 or response.status_code >= 500:
            raise RetryableError(f"GET {path} returned {response.status_code}: {response.text[:500]}")
        if response.status_code != 200:
            raise ArgoCDError(f"GET {path} returned {response.status_code}: {response.text[:500]}")
        return response.json()

    def check_access(self):
        # userinfo answers 200 even for a bad token, so loggedIn is the real check
        if not self.get("/api/v1/session/userinfo").get("loggedIn"):
            raise ArgoCDError("Argo CD rejected the token (session/userinfo reports loggedIn=false)")

    def list_applications(self):
        # One call returns every application with its full status, shared by both streams
        if self._applications is None:
            params = {}
            if self.projects:
                params["projects"] = self.projects
            if self.selector:
                params["selector"] = self.selector
            self._applications = self.get("/api/v1/applications", params).get("items") or []
            LOGGER.info("Fetched %s applications", len(self._applications))
        return self._applications
