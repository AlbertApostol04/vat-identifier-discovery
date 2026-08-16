"""
Step 3: pull VAT number candidates off the confirmed domains.

Only companies whose domain was proved in step 2 are visited. For each one
we fetch a handful of pages where UK companies normally put registration
details, not just the homepage: the VAT number and the Companies House
number usually live in a footer on /contact, /about or /terms.

Two things are extracted from every page:

  1. VAT candidates - the actual target.
  2. The Companies House number - not the target, but finding it upgrades
     our confidence that the domain really belongs to this company. Step 2
     confirmed 25 of 30 domains by name only, which is a weak signal; this
     is where that gets a second chance without extra requests.

Every candidate keeps the surrounding text. Without it the false positives
cannot be analysed later, and that analysis is half of the write-up.

Output: data/candidates.csv, one row per VAT candidate found.
"""

import re
import time

import pandas as pd
import requests

from vat_checksum import is_valid_vat

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; VATDiscoveryResearch/0.1; "
                  "student project; contact: albertzeutu@gmail.com)"
}

PAGES = ["", "/contact", "/contact-us", "/about", "/about-us",
         "/terms", "/privacy", "/legal"]

DELAY_BETWEEN_PAGES = 1.0
CONTEXT_CHARS = 100


GB_PREFIXED = re.compile(r"GB\s*(\d[\d\s]{7,15}\d)", re.IGNORECASE)


VAT_WORD = re.compile(r"\bVAT\b", re.IGNORECASE)


DIGIT_RUN = re.compile(r"\d[\d\s]{7,15}\d")


def readable_text(html):
    """Tags removed, whitespace collapsed to single spaces. Keeps it legible
    so the context snippets are actually readable in the CSV."""
    without_tags = re.sub(r"<[^>]+>", " ", html)
    return " ".join(without_tags.split())


def compact_text(text):
    """No whitespace at all. Used for identifier matching."""
    return "".join(text.split()).lower()


def only_digits(text):
    result = ""
    for character in text:
        if character.isdigit():
            result = result + character
    return result


def find_vat_candidates(text):
    """Return a list of (nine_digits, how_found, start, end).

    Two routes, because UK sites write it both ways:
      - an explicit GB prefix
      - the word VAT followed by the number a few characters later
    """
    hits = []

    for match in GB_PREFIXED.finditer(text):
        digits = only_digits(match.group(1))
        if len(digits) == 9:
            hits.append((digits, "gb_prefix", match.start(), match.end()))

    for word in VAT_WORD.finditer(text):
        window_start = word.end()
        window = text[window_start:window_start + 80]
        run = DIGIT_RUN.search(window)
        if run is None:
            continue
        digits = only_digits(run.group(0))
        if len(digits) == 9:
            hits.append((digits, "vat_keyword",
                         window_start + run.start(), window_start + run.end()))

    return hits


def fetch(domain, path):
    for scheme in ["https://", "http://"]:
        url = scheme + domain + path
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                return response.text, url
        except Exception:
            continue
    return None, None


if __name__ == "__main__":

    websites = pd.read_csv("data/websites.csv", dtype=str)
    confirmed = websites[websites["outcome"] == "found"]

    print("domains to visit: " + str(len(confirmed)))
    print("")

    rows = []
    domains_with_company_number = 0
    pages_fetched = 0
    started_at = time.time()

    for position in range(len(confirmed)):
        site = confirmed.iloc[position]
        domain = site["domain"]
        company_number = str(site["company_number"])
        company_name = str(site["company_name"])

        number_variants = [company_number, company_number.lstrip("0")]
        company_number_seen = False
        found_here = []

        for path in PAGES:
            html, url = fetch(domain, path)
            if html is None:
                continue
            pages_fetched = pages_fetched + 1

            text = readable_text(html)
            compact = compact_text(text)

            for variant in number_variants:
                if len(variant) >= 6 and variant in compact:
                    company_number_seen = True

            for digits, how, start, end in find_vat_candidates(text):
                snippet = text[max(0, start - CONTEXT_CHARS): end + CONTEXT_CHARS]
                found_here.append({
                    "company_number": company_number,
                    "company_name": company_name,
                    "stratum": site["stratum"],
                    "domain": domain,
                    "page_url": url,
                    "vat_candidate": digits,
                    "found_via": how,
                    "checksum_ok": is_valid_vat(digits),
                    "context": snippet,
                })

            time.sleep(DELAY_BETWEEN_PAGES)

        if company_number_seen:
            domains_with_company_number = domains_with_company_number + 1

        for row in found_here:
            row["company_number_on_site"] = company_number_seen
            rows.append(row)

        print(str(position + 1).rjust(3) + "/" + str(len(confirmed)) + "  " +
              domain.ljust(38) +
              "vat_candidates=" + str(len(found_here)) +
              "  company_number_seen=" + str(company_number_seen))

    candidates = pd.DataFrame(rows)
    candidates.to_csv("data/candidates.csv", index=False)

    elapsed = time.time() - started_at

    print("")
    print("elapsed: " + str(round(elapsed / 60, 1)) + " min")
    print("pages fetched: " + str(pages_fetched))
    print("")

    if len(candidates) == 0:
        print("No VAT candidates found at all.")
    else:
        print("--- CANDIDATES ---")
        print("raw candidates found : " + str(len(candidates)))
        print("passing checksum     : " + str(int(candidates["checksum_ok"].sum())))
        print("distinct companies   : " +
              str(candidates[candidates["checksum_ok"]]["company_number"].nunique()))
        print("")
        print("--- HOW THEY WERE FOUND ---")
        print(candidates["found_via"].value_counts())

    print("")
    print("--- DOMAIN ATTRIBUTION UPGRADE ---")
    print("domains where the Companies House number appeared: " +
          str(domains_with_company_number) + " / " + str(len(confirmed)))
    print("")
    print("Saved to data/candidates.csv")