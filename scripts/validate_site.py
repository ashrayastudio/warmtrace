#!/usr/bin/env python3
"""Dependency-free structural validation for the Warmtrace static site."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ORIGIN = "https://getwarmtrace.com"
PAGE_PATHS = {
    Path("index.html"): "/",
    Path("privacy/index.html"): "/privacy/",
    Path("support/index.html"): "/support/",
    Path("terms/index.html"): "/terms/",
}
FORBIDDEN_TEXT = (
    "google-analytics",
    "googletagmanager",
    "facebook.net",
    "segment.io",
    "mixpanel",
    "hotjar",
)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_depth = 0
        self.title = ""
        self.h1_count = 0
        self.main_count = 0
        self.description = ""
        self.canonical = ""
        self.internal_links: list[str] = []
        self.image_errors: list[str] = []
        self.script_count = 0
        self.skip_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title":
            self.title_depth += 1
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "main":
            self.main_count += 1
        elif tag == "script":
            self.script_count += 1
        elif tag == "meta" and values.get("name") == "description":
            self.description = values.get("content") or ""
        elif tag == "link" and values.get("rel") == "canonical":
            self.canonical = values.get("href") or ""
        elif tag == "a":
            href = values.get("href") or ""
            if values.get("class") == "skip-link" and href == "#main":
                self.skip_link = True
            if href.startswith("/"):
                self.internal_links.append(href)
        elif tag == "img":
            if "alt" not in values:
                self.image_errors.append(f"image {values.get('src', '<missing src>')} has no alt attribute")
            src = values.get("src") or ""
            if src.startswith("/"):
                self.internal_links.append(src)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self.title_depth:
            self.title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.title_depth:
            self.title += data


def local_target(reference: str) -> Path:
    path = urlsplit(reference).path
    candidate = ROOT / path.lstrip("/")
    if path.endswith("/"):
        candidate /= "index.html"
    return candidate


def main() -> int:
    errors: list[str] = []

    for relative_path, route in PAGE_PATHS.items():
        path = ROOT / relative_path
        if not path.is_file():
            errors.append(f"missing {relative_path}")
            continue
        source = path.read_text(encoding="utf-8")
        lowered = source.lower()
        parser = PageParser()
        parser.feed(source)

        if not parser.title.strip():
            errors.append(f"{relative_path}: missing title")
        if not parser.description.strip():
            errors.append(f"{relative_path}: missing meta description")
        if parser.h1_count != 1:
            errors.append(f"{relative_path}: expected one h1, found {parser.h1_count}")
        if parser.main_count != 1:
            errors.append(f"{relative_path}: expected one main, found {parser.main_count}")
        if not parser.skip_link:
            errors.append(f"{relative_path}: missing skip link")
        if parser.script_count:
            errors.append(f"{relative_path}: JavaScript is not permitted")
        expected_canonical = f"{CANONICAL_ORIGIN}{route}"
        if parser.canonical != expected_canonical:
            errors.append(
                f"{relative_path}: canonical is {parser.canonical!r}; expected {expected_canonical!r}"
            )
        errors.extend(f"{relative_path}: {message}" for message in parser.image_errors)
        for marker in FORBIDDEN_TEXT:
            if marker in lowered:
                errors.append(f"{relative_path}: forbidden tracker reference {marker}")
        for reference in parser.internal_links:
            target = local_target(reference)
            if not target.exists():
                errors.append(f"{relative_path}: broken internal reference {reference}")

    expected_files = (
        ".nojekyll",
        "404.html",
        "CNAME",
        "README.md",
        "robots.txt",
        "sitemap.xml",
        "styles.css",
        "assets/warmtrace-icon.png",
        "assets/apple-touch-icon.png",
        "assets/favicon-16.png",
        "assets/favicon-32.png",
        "assets/og.png",
        "assets/cormorant-garamond.ttf",
        "assets/dm-sans.ttf",
        "assets/cormorant-garamond-license.txt",
        "assets/dm-sans-license.txt",
    )
    for relative_path in expected_files:
        if not (ROOT / relative_path).is_file():
            errors.append(f"missing {relative_path}")

    if (ROOT / "CNAME").read_text(encoding="utf-8").strip() != "getwarmtrace.com":
        errors.append("CNAME must contain only getwarmtrace.com")

    try:
        sitemap = ET.parse(ROOT / "sitemap.xml")
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locations = {element.text for element in sitemap.findall("sm:url/sm:loc", namespace)}
        expected_locations = {f"{CANONICAL_ORIGIN}{route}" for route in PAGE_PATHS.values()}
        if locations != expected_locations:
            errors.append("sitemap routes do not exactly match the public page set")
    except (ET.ParseError, OSError) as error:
        errors.append(f"invalid sitemap: {error}")

    if errors:
        print("Warmtrace website validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Warmtrace website structural validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
