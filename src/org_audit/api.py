"""Small read-only GitHub REST client with bounded pagination and retries."""
from __future__ import annotations

import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

API = "https://api.github.com"


class AuditAPIError(RuntimeError):
    """Safe, actionable API failure without response bodies or credentials."""


class GitHubAPI:
    def __init__(self, token: str, *, opener=urlopen, sleep=time.sleep, timeout=15, retries=2):
        if not token or not token.strip():
            raise ValueError("GITHUB_TOKEN is required for live collection")
        self.token = token.strip()
        self.opener, self.sleep = opener, sleep
        self.timeout, self.retries = timeout, retries

    def get(self, path: str):
        url = urljoin(API + "/", path.lstrip("/"))
        if urlparse(url).netloc != "api.github.com" or not url.startswith(API + "/"):
            raise ValueError("API path must remain on api.github.com")
        request = Request(url, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + self.token,
            "User-Agent": "org-access-audit/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        }, method="GET")
        for attempt in range(self.retries + 1):
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    return json.load(response), dict(response.headers)
            except HTTPError as error:
                remaining = error.headers.get("X-RateLimit-Remaining", "") if error.headers else ""
                retryable = error.code in (429, 500, 502, 503, 504) or (error.code == 403 and remaining == "0")
                if retryable and attempt < self.retries:
                    error.close()
                    self.sleep(min(2 ** attempt, 4))
                    continue
                if error.code in (401, 403):
                    detail = "token invalid or insufficient read permissions" if remaining != "0" else "rate limit exhausted"
                elif error.code == 404:
                    detail = "resource unavailable or not visible to this token"
                else:
                    detail = "request failed"
                error.close()
                raise AuditAPIError(f"GitHub API {error.code}: {detail} ({urlparse(url).path})") from None
            except (URLError, TimeoutError, OSError):
                if attempt < self.retries:
                    self.sleep(min(2 ** attempt, 4))
                    continue
                raise AuditAPIError("GitHub API network failure; check connectivity and retry") from None
            except (ValueError, json.JSONDecodeError):
                raise AuditAPIError("GitHub API returned invalid JSON") from None
        raise AuditAPIError("GitHub API retry limit reached")

    def pages(self, path: str, *, max_pages=5):
        if not 1 <= max_pages <= 20:
            raise ValueError("max_pages must be between 1 and 20")
        url = path
        items = []
        for _ in range(max_pages):
            data, headers = self.get(url)
            if not isinstance(data, list):
                raise AuditAPIError("Expected a list from GitHub API")
            items.extend(data)
            match = re.search(r'<([^>]+)>;\s*rel="next"', headers.get("Link", ""))
            if not match:
                return items, False
            url = match.group(1)
            if not url.startswith(API + "/"):
                raise AuditAPIError("Pagination link escaped api.github.com")
        return items, True
