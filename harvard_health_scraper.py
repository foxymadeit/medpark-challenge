#!/usr/bin/env python3
"""
Harvard Health Medical Dictionary Scraper
==========================================
Scrapes all medical terms (A-Z) and their definitions from:
  https://www.health.harvard.edu/a-through-c
  https://www.health.harvard.edu/d-through-i
  https://www.health.harvard.edu/j-through-p
  https://www.health.harvard.edu/q-through-z

Strategy:
  1. PRIMARY:  Playwright headless browser (handles JS-rendered content)
  2. FALLBACK: BeautifulSoup4 + requests (static HTML parsing)

Output:
  - harvard_medical_dictionary.json  (structured dictionary A-Z)
  - harvard_medical_dictionary.csv   (flat term,definition,letter)
"""

import json
import csv
import re
import time
import logging
import sys
from pathlib import Path
from typing import Optional
from collections import OrderedDict

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = "https://www.health.harvard.edu"
PAGES = [
    {"url": f"{BASE_URL}/a-through-c", "letters": ["A", "B", "C"]},
    {"url": f"{BASE_URL}/d-through-i", "letters": ["D", "E", "F", "G", "H", "I"]},
    {"url": f"{BASE_URL}/j-through-p", "letters": ["J", "K", "L", "M", "N", "O", "P"]},
    {"url": f"{BASE_URL}/q-through-z", "letters": ["Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]},
]

OUTPUT_DIR = Path(__file__).parent
JSON_OUTPUT = OUTPUT_DIR / "harvard_medical_dictionary.json"
CSV_OUTPUT = OUTPUT_DIR / "harvard_medical_dictionary.csv"

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Blocklist patterns for promotional/junk content that uses the same
# <p><strong>...</strong> HTML pattern as real dictionary terms.
_JUNK_PATTERNS = [
    r"free\s+copy",
    r"special\s+health\s+report",
    r"living\s+longer",
    r"sign\s+up",
    r"subscribe",
    r"newsletter",
    r"harvard\s+health\s+publishing",
    r"click\s+here",
    r"learn\s+more",
    r"order\s+now",
    r"discount",
    r"32-page",
    r"bonus\s+report",
]
_JUNK_RE = re.compile("|".join(_JUNK_PATTERNS), re.IGNORECASE)


def _is_junk_term(term: str, definition: str) -> bool:
    """Return True if the term+definition looks like promotional content."""
    combined = f"{term} {definition}"
    if _JUNK_RE.search(combined):
        return True
    # Terms that are suspiciously long (real medical terms are short)
    if len(term) > 80:
        return True
    return False


def _clean_term(term: str) -> str:
    """Normalize a term string: strip trailing punctuation/noise."""
    # Remove trailing colon, question mark, whitespace
    term = re.sub(r"[:\s?]+$", "", term)
    # Collapse multiple internal spaces
    term = re.sub(r"\s{2,}", " ", term)
    return term.strip()


# ---------------------------------------------------------------------------
# Parsing logic (shared between Playwright & BS4)
# ---------------------------------------------------------------------------
def parse_terms_from_html(html: str) -> dict[str, list[dict[str, str]]]:
    """
    Parse medical terms and definitions from raw HTML.

    The page structure uses:
      - <a name="X-terms"></a> or <h2>X</h2> to mark letter sections
      - <p><strong>term: </strong>definition text</p> for each entry

    Returns:
        dict mapping uppercase letter -> list of {"term": ..., "definition": ...}
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    terms_by_letter: dict[str, list[dict[str, str]]] = OrderedDict()
    current_letter: Optional[str] = None

    # Track seen terms per letter for deduplication (keep first occurrence)
    seen_terms: dict[str, set[str]] = {}

    for element in soup.find_all(["h2", "p"]):
        # Check if this is a letter header
        if element.name == "h2":
            text = element.get_text(strip=True)
            if len(text) == 1 and text.isalpha():
                current_letter = text.upper()
                if current_letter not in terms_by_letter:
                    terms_by_letter[current_letter] = []
                    seen_terms[current_letter] = set()
                logger.debug(f"  Found section: {current_letter}")
                continue

        # Check if this is a term definition <p>
        if element.name == "p" and current_letter:
            strong_tag = element.find("strong")
            if not strong_tag:
                continue

            # Extract the term from the <strong> tag
            term_text = strong_tag.get_text(strip=True)

            # Clean up the term
            term_text = _clean_term(term_text)

            if not term_text:
                continue

            # Extract the full paragraph text, then remove the term portion
            # to get just the definition
            full_text = element.get_text(separator=" ", strip=True)

            # Remove the term (and colon) from the beginning of the full text
            # to isolate the definition
            definition = full_text
            term_pattern = re.escape(term_text)
            # Match term followed by optional stray punctuation (? ! etc), colon, space
            match = re.match(
                rf"^{term_pattern}[?!.,;]*\s*:?\s*", definition, re.IGNORECASE
            )
            if match:
                definition = definition[match.end() :].strip()

            if not definition:
                continue

            # --- FILTERS ---

            # Skip promotional/junk content
            if _is_junk_term(term_text, definition):
                logger.debug(f"  Skipped junk: {term_text[:50]}")
                continue

            # Deduplicate: skip if we've already seen this term in this letter
            term_key = term_text.lower().strip()
            if term_key in seen_terms[current_letter]:
                logger.debug(f"  Skipped duplicate: {term_text}")
                continue
            seen_terms[current_letter].add(term_key)

            terms_by_letter[current_letter].append(
                {"term": term_text, "definition": definition}
            )

    return terms_by_letter


# ---------------------------------------------------------------------------
# Playwright scraper (primary)
# ---------------------------------------------------------------------------
def scrape_with_playwright() -> dict[str, list[dict[str, str]]]:
    """
    Scrape all pages using Playwright headless Chromium browser.
    Uses playwright-stealth to avoid bot detection.
    """
    logger.info("=" * 60)
    logger.info("ATTEMPTING: Playwright headless scraper")
    logger.info("=" * 60)

    from playwright.sync_api import sync_playwright
    from playwright_stealth import stealth_sync

    all_terms: dict[str, list[dict[str, str]]] = OrderedDict()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # Apply stealth to avoid detection
        stealth_sync(page)

        for page_info in PAGES:
            url = page_info["url"]
            letters = page_info["letters"]
            logger.info(f"Scraping: {url}  (letters: {', '.join(letters)})")

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    page.goto(url, wait_until="networkidle", timeout=60000)
                    # Wait for actual dictionary content (p > strong tags)
                    page.wait_for_selector(
                        "p strong", state="attached", timeout=20000
                    )
                    # Small delay for any lazy-loaded content
                    page.wait_for_timeout(2000)

                    html = page.content()
                    terms = parse_terms_from_html(html)

                    for letter in letters:
                        if letter in terms and terms[letter]:
                            all_terms[letter] = terms[letter]
                            logger.info(
                                f"  ✓ Letter {letter}: {len(terms[letter])} terms"
                            )
                        else:
                            logger.warning(f"  ✗ Letter {letter}: no terms found")
                            all_terms.setdefault(letter, [])

                    break  # Success — no need to retry

                except Exception as e:
                    logger.warning(
                        f"  Attempt {attempt}/{MAX_RETRIES} failed: {e}"
                    )
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY)
                    else:
                        raise

        browser.close()

    return all_terms


# ---------------------------------------------------------------------------
# BeautifulSoup4 + requests scraper (fallback)
# ---------------------------------------------------------------------------
def scrape_with_bs4() -> dict[str, list[dict[str, str]]]:
    """
    Fallback scraper using requests + BeautifulSoup4 for static HTML parsing.
    """
    logger.info("=" * 60)
    logger.info("ATTEMPTING: BeautifulSoup4 fallback scraper")
    logger.info("=" * 60)

    import requests

    all_terms: dict[str, list[dict[str, str]]] = OrderedDict()

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": BASE_URL,
        }
    )

    for page_info in PAGES:
        url = page_info["url"]
        letters = page_info["letters"]
        logger.info(f"Scraping: {url}  (letters: {', '.join(letters)})")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = session.get(url, timeout=30)
                response.raise_for_status()

                terms = parse_terms_from_html(response.text)

                for letter in letters:
                    if letter in terms and terms[letter]:
                        all_terms[letter] = terms[letter]
                        logger.info(
                            f"  ✓ Letter {letter}: {len(terms[letter])} terms"
                        )
                    else:
                        logger.warning(f"  ✗ Letter {letter}: no terms found")
                        all_terms.setdefault(letter, [])

                break  # Success

            except Exception as e:
                logger.warning(
                    f"  Attempt {attempt}/{MAX_RETRIES} failed: {e}"
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    raise

        # Polite delay between pages
        time.sleep(2)

    return all_terms


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
def save_json(terms: dict[str, list[dict[str, str]]], path: Path) -> None:
    """Save the dictionary as a nicely formatted JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(terms, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved JSON: {path}")


def save_csv(terms: dict[str, list[dict[str, str]]], path: Path) -> None:
    """Save the dictionary as a flat CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["letter", "term", "definition"])
        for letter, entries in terms.items():
            for entry in entries:
                writer.writerow([letter, entry["term"], entry["definition"]])
    logger.info(f"Saved CSV:  {path}")


def print_summary(terms: dict[str, list[dict[str, str]]]) -> None:
    """Print a summary of scraped terms."""
    total = sum(len(v) for v in terms.values())
    logger.info("=" * 60)
    logger.info("SCRAPE SUMMARY")
    logger.info("=" * 60)
    for letter in sorted(terms.keys()):
        count = len(terms[letter])
        logger.info(f"  {letter}: {count:>4} terms")
    logger.info(f"  {'─' * 20}")
    logger.info(f"  TOTAL: {total} terms across {len(terms)} letters")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    """
    Run the scraper with Playwright as primary and BS4 as fallback.
    """
    terms = None
    method_used = None

    # ----- PRIMARY: Playwright -----
    try:
        terms = scrape_with_playwright()
        method_used = "Playwright"
    except Exception as e:
        logger.error(f"Playwright scraper failed: {e}")
        logger.info("Falling back to BeautifulSoup4...")

    # ----- FALLBACK: BS4 -----
    if terms is None or not any(terms.values()):
        try:
            terms = scrape_with_bs4()
            method_used = "BeautifulSoup4"
        except Exception as e:
            logger.error(f"BeautifulSoup4 fallback also failed: {e}")
            sys.exit(1)

    if not terms or not any(terms.values()):
        logger.error("No terms were scraped. Exiting.")
        sys.exit(1)

    # ----- Save outputs -----
    logger.info(f"\nSuccessfully scraped using: {method_used}")
    save_json(terms, JSON_OUTPUT)
    save_csv(terms, CSV_OUTPUT)
    print_summary(terms)

    # ----- Quick preview -----
    logger.info("\n📖 Sample entries:")
    for letter in ["A", "M", "Z"]:
        if letter in terms and terms[letter]:
            entry = terms[letter][0]
            logger.info(f'  [{letter}] {entry["term"]}: {entry["definition"][:80]}...')


if __name__ == "__main__":
    main()
