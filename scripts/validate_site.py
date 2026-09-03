#!/usr/bin/env python3
"""Dependency-free structural validation for the Warmtrace static site."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import parse_qsl, unquote, urlsplit
from html import unescape
import sys
import tempfile
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
FORBIDDEN_PUBLIC_IDENTITY = (
    "ashraya",
    "ashrayastudio",
    "ashraya-operated",
    "©",
)
LEGAL_OPERATOR_NAME = "Kalpesh Patel"
CONTROLLER_DISCLOSURE = f"The data controller is {LEGAL_OPERATOR_NAME}."
APPROVED_PUBLIC_EMAIL = "appportfolio.contact@gmail.com"
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


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
        self.form_count = 0
        self.embedded_count = 0
        self.resource_dependencies: list[str] = []
        self.attribute_values: list[str] = []
        self.rendered_text: list[str] = []
        self.ignored_depth = 0
        self.skip_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        self.attribute_values.extend(value for value in values.values() if value)
        if tag in {"style", "script"}:
            self.ignored_depth += 1
        if tag == "title":
            self.title_depth += 1
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "main":
            self.main_count += 1
        elif tag == "script":
            self.script_count += 1
            if values.get("src"):
                self.resource_dependencies.append(values["src"] or "")
        elif tag == "form":
            self.form_count += 1
        elif tag in {"iframe", "object", "embed"}:
            self.embedded_count += 1
            reference = values.get("src") or values.get("data") or ""
            if reference:
                self.resource_dependencies.append(reference)
        elif tag == "meta" and values.get("name") == "description":
            self.description = values.get("content") or ""
        elif tag == "link" and values.get("rel") == "canonical":
            self.canonical = values.get("href") or ""
        elif tag == "link":
            href = values.get("href") or ""
            if href:
                self.resource_dependencies.append(href)
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
            if src:
                self.resource_dependencies.append(src)
            if src.startswith("/"):
                self.internal_links.append(src)
        elif tag in {"audio", "video", "source", "track"}:
            reference = values.get("src") or values.get("poster") or ""
            if reference:
                self.resource_dependencies.append(reference)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self.title_depth:
            self.title_depth -= 1
        if tag in {"style", "script"} and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.title_depth:
            self.title += data
        if not self.ignored_depth:
            normalized = " ".join(data.split())
            if normalized:
                self.rendered_text.append(normalized)


def local_target(reference: str) -> Path:
    path = urlsplit(reference).path
    candidate = ROOT / path.lstrip("/")
    if path.endswith("/"):
        candidate /= "index.html"
    return candidate


def repository_html_paths(root: Path = ROOT) -> list[Path]:
    """Return every public HTML source while excluding Git internals."""
    return sorted(
        path.relative_to(root)
        for path in root.rglob("*.html")
        if ".git" not in path.relative_to(root).parts
    )


def public_policy_errors(
    source: str,
    parser: PageParser,
    *,
    allow_controller_disclosure: bool = False,
) -> list[str]:
    errors: list[str] = []
    lowered = source.lower()
    rendered_text = " ".join(parser.rendered_text)
    public_surface_text = " ".join(
        [
            parser.title,
            parser.description,
            *parser.rendered_text,
            *parser.attribute_values,
        ]
    ).lower()
    public_surface_text = unquote(unescape(public_surface_text))
    for marker in FORBIDDEN_PUBLIC_IDENTITY:
        if marker.lower() in lowered or marker.lower() in public_surface_text:
            errors.append(f"forbidden public identity marker {marker}")
    operator_name_count = public_surface_text.count(LEGAL_OPERATOR_NAME.lower())
    if allow_controller_disclosure:
        if (
            source.count(CONTROLLER_DISCLOSURE) != 1
            or rendered_text.count(CONTROLLER_DISCLOSURE) != 1
            or operator_name_count != 1
        ):
            errors.append("privacy page must contain exactly one approved controller disclosure")
    elif LEGAL_OPERATOR_NAME.lower() in lowered or operator_name_count:
        errors.append(f"forbidden public identity marker {LEGAL_OPERATOR_NAME}")
    if parser.script_count:
        errors.append("JavaScript is not permitted")
    if parser.form_count:
        errors.append("forms are not permitted")
    if parser.embedded_count:
        errors.append("embedded remote content is not permitted")
    for reference in parser.resource_dependencies:
        parsed = urlsplit(reference)
        if parsed.scheme in {"http", "https"} or reference.startswith("//"):
            errors.append(f"external runtime dependency {reference}")
    for email in EMAIL_PATTERN.findall(public_surface_text):
        if email.casefold() != APPROVED_PUBLIC_EMAIL:
            errors.append("email outside approved exact mailbox")
    for reference in parser.attribute_values:
        decoded = unquote(reference)
        if decoded.casefold().startswith("mailto:"):
            parsed = urlsplit(decoded)
            headers = parse_qsl(parsed.query, keep_blank_values=True)
            if (
                parsed.path.casefold() != APPROVED_PUBLIC_EMAIL
                or parsed.netloc
                or parsed.fragment
                or any(ord(character) < 32 for character in decoded)
                or any(key != "subject" or not value or any(ord(character) < 32 for character in value) for key, value in headers)
                or len(headers) != 1
                or not headers[0][1].startswith("Warmtrace ")
            ):
                errors.append("unapproved support mail link")
    return errors


def run_self_test() -> int:
    cases = (
        ("<p>Ashraya&#32;Studio</p>", "forbidden public identity marker"),
        ('<a href="mailto:hello@ashraya.ai">Support</a>', "forbidden public identity marker"),
        ('<a href="mailto:help@example.com">Support</a>', "email outside approved exact mailbox"),
        ('<a href="mailto:help@getwarmtrace.com">Support</a>', "email outside approved exact mailbox"),
        ("<p>Kalpesh Patel</p>", "forbidden public identity marker"),
        ("<p>&copy; 2026</p>", "forbidden public identity marker"),
        ("<form></form>", "forms are not permitted"),
        ("<script></script>", "JavaScript is not permitted"),
        ('<img src="https://example.invalid/pixel.png" alt="">', "external runtime dependency"),
        ('<iframe src="/remote"></iframe>', "embedded remote content is not permitted"),
    )
    for source, expected in cases:
        parser = PageParser()
        parser.feed(source)
        if not any(expected in error for error in public_policy_errors(source, parser)):
            print(f"self-test did not reject {expected}", file=sys.stderr)
            return 1

    for address in ("other@gmail.com", "appportfolio.contact+app@gmail.com", "appportfoliocontact@gmail.com", "appportfolio.contact@gmail.com.evil.example", "appportfolio.contact@sub.gmail.com"):
        source = f'<a href="mailto:{address}?subject=Warmtrace%20support">Contact</a>'
        parser = PageParser()
        parser.feed(source)
        if not public_policy_errors(source, parser):
            print("self-test accepted an unapproved mailbox", file=sys.stderr)
            return 1
    for suffix in ("&amp;cc=other%40gmail.com", "&amp;bcc=other%40gmail.com", "&amp;subject=duplicate", "%0D%0ABcc%3Aother%40gmail.com"):
        source = f'<a href="mailto:{APPROVED_PUBLIC_EMAIL}?subject=Warmtrace%20support{suffix}">Contact</a>'
        parser = PageParser()
        parser.feed(source)
        if not public_policy_errors(source, parser):
            print("self-test accepted an unsafe mail header", file=sys.stderr)
            return 1
    accepted = f'<a href="mailto:{APPROVED_PUBLIC_EMAIL}?subject=Warmtrace%20support">{APPROVED_PUBLIC_EMAIL}</a>'
    parser = PageParser()
    parser.feed(accepted)
    if public_policy_errors(accepted, parser):
        print("self-test rejected the contact-unavailable fixture", file=sys.stderr)
        return 1

    accepted_privacy = f"<p>{CONTROLLER_DISCLOSURE}</p>"
    parser = PageParser()
    parser.feed(accepted_privacy)
    if public_policy_errors(accepted_privacy, parser, allow_controller_disclosure=True):
        print("self-test rejected the exact privacy controller disclosure", file=sys.stderr)
        return 1

    rejected_privacy_cases = (
        f"<p>{CONTROLLER_DISCLOSURE}</p><p>{CONTROLLER_DISCLOSURE}</p>",
        f"<p>{LEGAL_OPERATOR_NAME} is the data controller.</p>",
    )
    for source in rejected_privacy_cases:
        parser = PageParser()
        parser.feed(source)
        if not any(
            "exactly one approved controller disclosure" in error
            for error in public_policy_errors(
                source,
                parser,
                allow_controller_disclosure=True,
            )
        ):
            print("self-test accepted non-standard privacy controller copy", file=sys.stderr)
            return 1
    with tempfile.TemporaryDirectory(prefix="warmtrace-site-validator.") as temporary:
        root = Path(temporary)
        future = root / "future" / "nested.html"
        future.parent.mkdir(parents=True)
        future.write_text("<p>Future</p>", encoding="utf-8")
        if repository_html_paths(root) != [Path("future/nested.html")]:
            print("self-test did not discover a nested future HTML page", file=sys.stderr)
            return 1
    print("Warmtrace website validator self-test passed.")
    return 0


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
        if relative_path in {Path("support/index.html"), Path("privacy/index.html"), Path("terms/index.html")}:
            if not any(value.startswith(f"mailto:{APPROVED_PUBLIC_EMAIL}?subject=Warmtrace%20") for value in parser.attribute_values):
                errors.append(f"{relative_path}: missing approved support mail link")

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
        errors.extend(
            f"{relative_path}: {message}"
            for message in public_policy_errors(
                source,
                parser,
                allow_controller_disclosure=relative_path == Path("privacy/index.html"),
            )
        )
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

    # Route-specific structure and canonical rules above apply only to the
    # approved page set. Identity, controller, script/form/embed, external-
    # dependency, and tracker policy must fail closed across every HTML source,
    # including 404.html and any future page.
    for relative_path in repository_html_paths():
        if relative_path in PAGE_PATHS:
            continue
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        parser = PageParser()
        parser.feed(source)
        errors.extend(
            f"{relative_path}: {message}"
            for message in public_policy_errors(source, parser)
        )
        for marker in FORBIDDEN_TEXT:
            if marker in source.lower():
                errors.append(f"{relative_path}: forbidden tracker reference {marker}")

    expected_files = (
        ".nojekyll",
        "404.html",
        "AGENTS.md",
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

    agents_path = ROOT / "AGENTS.md"
    if agents_path.is_file():
        agents = agents_path.read_text(encoding="utf-8")
        for marker in (
            "https://github.com/ashrayastudio/warmtrace.git",
            "`gh` CLI",
            "macOS-keyring-backed credential helper",
            "Hermes is a bounded backup",
            "A sandbox denial requires narrow escalation",
            "D-016",
            "D-027",
        ):
            if marker not in agents:
                errors.append(f"AGENTS.md missing governance marker {marker}")
        for obsolete in (
            "/Users/hermes/.local/bin/hermes -z",
            "exclusive operator",
        ):
            if obsolete in agents:
                errors.append(f"AGENTS.md contains obsolete governance marker {obsolete}")

    stylesheet = (ROOT / "styles.css").read_text(encoding="utf-8")
    if "@import" in stylesheet or "http://" in stylesheet or "https://" in stylesheet:
        errors.append("styles.css must not import external runtime resources")

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
    raise SystemExit(run_self_test() if "--self-test" in sys.argv[1:] else main())
