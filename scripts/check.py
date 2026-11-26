#!/usr/bin/env python3
"""Check generated digest pages, RSS enclosures and optionally today's inputs."""
import argparse
from datetime import datetime
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent


class HeadRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith(("https://", "http://")):
            raise HTTPError(req.full_url, code, "redirect is not HTTP(S)", headers, fp)
        redirect = super().redirect_request(req, fp, code, msg, headers, newurl)
        redirect.method = req.get_method()
        return redirect


def check_enclosure(opener, enclosure):
    url, length = enclosure.get("url", ""), enclosure.get("length", "")
    if not url.lower().startswith(("https://", "http://")):
        return f"invalid enclosure URL: {url!r}"
    if not (length.isascii() and length.isdecimal()):
        return f"{url}: invalid enclosure length {length!r}"
    for _ in range(3):
        try:
            req = Request(url, headers={"User-Agent": "x-ai-daily-check/1.0"}, method="HEAD")
            with opener.open(req, timeout=20) as resp:
                actual = resp.headers.get("Content-Length", "").strip()
                if resp.status != 200:
                    error = f"HTTP {resp.status}, expected 200"
                elif not (actual.isascii() and actual.isdecimal() and int(actual) == int(length)):
                    error = f"Content-Length {actual!r}, expected {length}"
                else:
                    return None
        except (OSError, ValueError, HTTPException) as exc:
            error = str(exc)
    return f"{url}: {error}"


def check(today):
    errors = []
    try:
        feed = ET.parse(ROOT / "podcast.xml")
    except (OSError, ET.ParseError) as exc:
        errors.append(f"podcast.xml: {exc}")
    else:
        opener = build_opener(HeadRedirect())
        for enclosure in feed.iter("enclosure"):
            error = check_enclosure(opener, enclosure)
            if error:
                errors.append(error)
    for md in sorted((ROOT / "digests").glob("*.md")):
        if not md.with_suffix(".html").is_file():
            errors.append(f"missing digests/{md.stem}.html")
    if today:
        date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        for path in (f"digests/{date}.md", f"podcast/{date}.json"):
            if not (ROOT / path).is_file():
                errors.append(f"missing {path} (Beijing today)")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--today", action="store_true", help="require today's Beijing digest and podcast metadata")
    errors = check(parser.parse_args().today)
    if errors:
        parser.exit(1, "\n".join(errors) + "\n")
    print("Site checks passed.")


if __name__ == "__main__":
    main()
