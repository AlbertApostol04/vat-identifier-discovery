"""
Step 2: find a website for each company in the sample.

Companies House has no website field, so the domain has to be guessed and then proved.
Guessing is cheap and produces a lot of rubbish; the proof is what makes the result usable.

A UK company must display its registration number on its website (Companies Act 2006).
That number is the primary key from Companies House,so finding it on a page is close to conclusive evidence that the page belongs to that company.
Falling back to the company name is much weaker
and is recorded separately.

Output: data/websites.csv, one row per company, with an `outcome` columnthat says how far down the funnel each company got."""

import re
import socket
import time

import pandas as pd
import requests

socket.setdefaulttimeout(3)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; VATDiscoveryResearch/0.1; "
                  "student project; contact: albertzeutu@gmail.com)"
}

LEGAL_SUFFIXES = [
    "LIMITED", "LTD", "PLC", "LLP", "LP", "CIC", "CIO",
    "COMPANY", "CO", "HOLDINGS", "GROUP",
]

TLDS = [".co.uk", ".com", ".uk"]

MAX_CANDIDATES = 6
DELAY_BETWEEN_COMPANIES = 0.5




def normalise_name(name):
    """'J. SMITH & SONS (BUILDING) LTD' -> ['j', 'smith', 'and', 'sons', 'building']"""
    text = str(name).upper().replace("&", " AND ")

    cleaned = ""
    for character in text:
        if character.isalnum():
            cleaned = cleaned + character
        else:
            cleaned = cleaned + " "

    words = cleaned.split()

    kept = []
    for word in words:
        if word not in LEGAL_SUFFIXES:
            kept.append(word)

    return [w.lower() for w in kept]


def guess_domains(name, max_candidates=MAX_CANDIDATES):
    words = normalise_name(name)
    if len(words) == 0:
        return []

    stems = []
    stems.append("".join(words))
    if len(words) >= 2:
        stems.append("".join(words[:2]))
        stems.append("-".join(words))
    if len(words) >= 3:
        stems.append("".join(words[:3]))

    usable_stems = []
    for stem in stems:
        if stem not in usable_stems and 3 <= len(stem) <= 40:
            usable_stems.append(stem)

    candidates = []
    for stem in usable_stems:
        for tld in TLDS:
            candidate = stem + tld
            if candidate not in candidates:
                candidates.append(candidate)

    return candidates[:max_candidates]


def domain_resolves(domain):
    """DNS lookup only - about 20ms, versus 1-3s for an HTTP request."""
    try:
        socket.gethostbyname(domain)
        return True
    except Exception:
        return False


def fetch(domain):
    """Try HTTPS first, then HTTP. Many small UK company sites have no TLS."""
    for scheme in ["https://", "http://"]:
        try:
            response = requests.get(scheme + domain, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                return response.text
        except Exception:
            continue
    return None



def compact_text(html):
    """Strip HTML tags, then remove all whitespace, then lowercase.

    Removing tags first matters: a name can be split across markup,
    e.g. <span>J</span> Smith Building Services.
    """
    without_tags = re.sub(r"<[^>]+>", " ", html)
    return "".join(without_tags.split()).lower()


def identify_page(html, company_number, company_name):
    """Return 'company_number', 'company_name', or None.

    Company number is checked first because it is a near-certain match.
    The name is a much weaker signal and is reported separately so the
    two are never mixed up downstream.
    """
    compact = compact_text(html)

    for variant in [str(company_number), str(company_number).lstrip("0")]:
        if len(variant) >= 6 and variant.lower() in compact:
            return "company_number"

    joined_name = "".join(normalise_name(company_name))
    if len(joined_name) >= 8 and joined_name in compact:
        return "company_name"

    return None




if __name__ == "__main__":

    sample = pd.read_csv("data/sample.csv", dtype=str)


    # sample = sample.head(20)

    total = len(sample)
    started_at = time.time()
    results = []

    for position in range(total):
        row = sample.iloc[position]
        company_number = row["CompanyNumber"]
        company_name = row["CompanyName"]

        candidates = guess_domains(company_name)

        any_resolved = False
        any_fetched = False
        found_domain = ""
        matched_by = ""

        for candidate in candidates:
            if not domain_resolves(candidate):
                continue
            any_resolved = True

            html = fetch(candidate)
            if html is None:
                continue
            any_fetched = True

            match = identify_page(html, company_number, company_name)
            if match is not None:
                found_domain = candidate
                matched_by = match
                break


        if matched_by != "":
            outcome = "found"
        elif any_fetched:
            outcome = "no_match"
        elif any_resolved:
            outcome = "no_http"
        else:
            outcome = "no_dns"

        results.append({
            "company_number": company_number,
            "company_name": company_name,
            "stratum": row["stratum"],
            "candidates_tried": len(candidates),
            "domain": found_domain,
            "matched_by": matched_by,
            "outcome": outcome,
        })

        print(str(position + 1).rjust(3) + "/" + str(total) + "  " +
              outcome.ljust(10) + str(company_name)[:45])

        time.sleep(DELAY_BETWEEN_COMPANIES)

    websites = pd.DataFrame(results)
    websites.to_csv("data/websites.csv", index=False)

    elapsed = time.time() - started_at

    print("")
    print("elapsed: " + str(round(elapsed / 60, 1)) + " min for " + str(total) + " companies")
    print("")
    print("--- OUTCOME ---")
    print(websites["outcome"].value_counts())
    print("")
    print("--- MATCHED BY (found only) ---")
    print(websites[websites["outcome"] == "found"]["matched_by"].value_counts())
    print("")
    print("--- OUTCOME BY STRATUM ---")
    print(pd.crosstab(websites["stratum"], websites["outcome"]))
    print("")
    print("Saved to data/websites.csv")
