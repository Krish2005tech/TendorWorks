"""Controlled public-source discovery. Results are candidates, never automatic official rates."""

import hashlib
import ipaddress
import socket
from datetime import date
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from tender.ingestion import extract
from tender.knowledge import KnowledgeGateway, key
from tender.schemas import SourceDocument


def allowed_url(url: str, hosts: list[str]) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        return False
    if not any(host == entry or host.endswith("." + entry) for entry in hosts):
        return False
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(entry[4][0]).is_global for entry in addresses)
    except (OSError, ValueError):
        return False


class ResearchWorker:
    def __init__(self, gateway: KnowledgeGateway):
        self.gateway, self.settings = gateway, gateway.settings

    def discover(self, authority: str, component_key: str, tenant: str) -> dict:
        if not self.settings.web_enabled or not self.settings.web_search_key:
            return {"status": "disabled", "candidates": []}
        # No project title, description, address, capacity or uploaded content leaves the server.
        query = f"{authority} schedule of rates {component_key.replace('_', ' ')} official"
        response = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": 5},
            headers={"X-Subscription-Token": self.settings.web_search_key},
            timeout=20,
        )
        response.raise_for_status()
        results, errors = [], []
        for item in response.json().get("web", {}).get("results", []):
            if len(results) >= self.settings.max_research_documents:
                break
            url = item.get("url", "")
            try:
                if not allowed_url(url, self.settings.web_allowed_hosts):
                    continue
                doc_id = self.fetch(url, item.get("title", component_key), authority, tenant)
                results.append(doc_id)
            except (httpx.HTTPError, ValueError, OSError) as exc:
                errors.append(str(exc)[:200])
        return {"status": "candidates_require_review", "candidates": results, "errors": errors}

    def fetch(self, url: str, title: str, authority: str, tenant: str) -> str:
        for _ in range(4):
            if not allowed_url(url, self.settings.web_allowed_hosts):
                raise ValueError("Source host is not permitted")
            with httpx.stream(
                "GET",
                url,
                timeout=25,
                follow_redirects=False,
                headers={"User-Agent": "TenderEstimator/0.1 source-research"},
            ) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers.get("location", ""))
                    continue
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > self.settings.max_upload_bytes:
                        raise ValueError("Research source exceeds size limit")
                raw = bytes(content)
                if "application/pdf" in response.headers.get("content-type", "") or raw.startswith(b"%PDF"):
                    text = extract(raw, ".pdf")
                else:
                    soup = BeautifulSoup(raw, "html.parser")
                    for tag in soup(["script", "style", "nav"]):
                        tag.decompose()
                    text = soup.get_text("\n", strip=True)[:500000]
                digest = hashlib.sha256(raw).hexdigest()
                document = SourceDocument(
                    id=key(url, digest),
                    title=title,
                    version=digest[:12],
                    kind="web",
                    authority=authority,
                    effective_from=date(1900, 1, 1),
                    url=url,
                    text=text,
                    locator="Publication and effective dates require review",
                    trust="candidate",
                    snapshot_ref=self.gateway.objects.put(raw),
                    content_hash=digest,
                )
                return self.gateway.index_document(document, tenant, "research")
        raise ValueError("Too many source redirects")
