from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen


DEFAULT_RULES_PAGE_URL = "https://magic.wizards.com/en/rules"
ALLOWED_RULES_HOSTS = {"magic.wizards.com"}
ALLOWED_TXT_HOSTS = {"media.wizards.com", "magic.wizards.com"}


@dataclass(frozen=True)
class FetchedRules:
    text: str
    url: str


class OfficialRulesSource:
    def __init__(
        self,
        rules_page_url: str = DEFAULT_RULES_PAGE_URL,
        timeout_seconds: int = 30,
        max_bytes: int = 25_000_000,
    ) -> None:
        _validate_https_url(rules_page_url, ALLOWED_RULES_HOSTS)
        self.rules_page_url = rules_page_url
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    def fetch_latest_rules_txt(self) -> FetchedRules:
        html = self._fetch_text(self.rules_page_url, ALLOWED_RULES_HOSTS)
        txt_url = extract_txt_link(html, self.rules_page_url)
        text = self._fetch_text(txt_url, ALLOWED_TXT_HOSTS)
        return FetchedRules(text=text, url=txt_url)

    def _fetch_text(self, url: str, allowed_hosts: set[str]) -> str:
        _validate_https_url(url, allowed_hosts)
        request = Request(url, headers={"User-Agent": "mtg-rules-etl/1.0"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = response.read(self.max_bytes + 1)
        if len(payload) > self.max_bytes:
            raise ValueError(f"Response exceeded {self.max_bytes} bytes: {url}")
        return payload.decode("utf-8-sig")


def extract_txt_link(html: str, base_url: str) -> str:
    parser = _AnchorParser()
    parser.feed(html)
    candidates = []
    for href, label in parser.links:
        absolute = _quote_url(urljoin(base_url, href))
        parsed = urlparse(absolute)
        if parsed.path.lower().endswith(".txt"):
            candidates.append((absolute, label.strip().upper()))
    if not candidates:
        raise ValueError("No TXT link was found on the rules page.")
    txt_labeled = [url for url, label in candidates if label == "TXT"]
    selected = txt_labeled[0] if txt_labeled else candidates[0][0]
    _validate_https_url(selected, ALLOWED_TXT_HOSTS)
    return selected


def _quote_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            quote(parsed.path, safe="/%"),
            parsed.params,
            quote(parsed.query, safe="=&%/:?+"),
            parsed.fragment,
        )
    )


def _validate_https_url(url: str, allowed_hosts: set[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Only HTTPS URLs are allowed: {url}")
    if parsed.hostname not in allowed_hosts:
        raise ValueError(f"Host is not allowed for this ETL: {parsed.hostname}")


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        if href:
            self._current_href = href
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current_href:
            self.links.append((self._current_href, "".join(self._current_text)))
            self._current_href = None
            self._current_text = []
