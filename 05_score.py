"""

Step 5: decide whether each VAT number really belongs to the company.

This is the step the whole project exists for. A valid VAT number attached to the wrong company is invisible in the output and corrupts every join the customer makes downstream,
so validity alone is not enough - the question is attribution.

HMRC returns the registered name and address for a number, so attribution can be checked:
compare what HMRC says against what Companies House says.

Two signals, weighted differently:

  name      compared against both the current and the previous Companies
            House name, because HMRC may still hold an older one

  postcode  only used when it discriminates. In this sample the median
            postcode is shared by 9 companies but the maximum is shared by
            59,168, so "the postcode matches" means nothing for a company
            registered at a formation agent's address. Threshold: 20.

Output: data/results.csv, one row for every company in the sample - not just the ones with a candidate.
The companies with nothing found are the result too, and dropping them would quietly flatter the numbers."""

from difflib import SequenceMatcher

import pandas as pd

NAME_STRONG = 0.85          # accept on the name alone
NAME_WEAK = 0.65            # accept only with a discriminating postcode
POSTCODE_USEFUL_BELOW = 20  # from the measured distribution of the sample

LEGAL_SUFFIXES = [
    "LIMITED", "LTD", "PLC", "LLP", "LP", "CIC", "CIO",
    "COMPANY", "CO", "HOLDINGS", "GROUP", "THE",
]


def normalise(name):
    """Bring both sides to the same shape before comparing them.

    HMRC writes 'UBER LONDON LIMITED', Companies House may write 'UBER LONDON LTD'. Neither spelling is wrong; comparing them raw is.

    Missing values return "" rather than the string "nan",so that two absent names do not score as a perfect match against each other.
    """
    if name is None:
        return ""

    text = str(name)
    if text.strip().lower() in ("", "nan", "none"):
        return ""

    text = text.upper().replace("&", " AND ")

    cleaned = ""
    for character in text:
        if character.isalnum():
            cleaned = cleaned + character
        else:
            cleaned = cleaned + " "

    words = []
    for word in cleaned.split():
        if word not in LEGAL_SUFFIXES:
            words.append(word)

    return " ".join(words)

def similarity(left, right):
    a, b = normalise(left), normalise(right)
    if a == "" or b == "":
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def tidy_postcode(value):
    return "".join(str(value).split()).upper()


def decide(row):
    """Return (status, reason)."""
    if str(row["hmrc_valid"]).strip().lower() not in ("true", "1", "yes"):
        return "INVALID", "HMRC rejected the number"

    name_score = max(
        similarity(row["hmrc_name"], row["company_name"]),
        similarity(row["hmrc_name"], row["ch_previous_name"]),
    )

    postcodes_match = (
        tidy_postcode(row["hmrc_postcode"]) == tidy_postcode(row["ch_postcode"])
        and tidy_postcode(row["ch_postcode"]) != ""
    )

    try:
        shared = float(row["postcode_company_count"])
    except (ValueError, TypeError):
        shared = 999999
    postcode_discriminates = shared <= POSTCODE_USEFUL_BELOW

    if name_score >= NAME_STRONG:
        return "CONFIRMED", f"name {name_score:.2f}"

    if name_score >= NAME_WEAK and postcodes_match and postcode_discriminates:
        return "CONFIRMED", f"name {name_score:.2f} + postcode shared by {int(shared)}"

    if name_score >= NAME_WEAK:
        return "NEEDS_REVIEW", f"name {name_score:.2f}, postcode not decisive"

    return "MISMATCH", f"name {name_score:.2f} - HMRC says '{row['hmrc_name']}'"


if __name__ == "__main__":

    sample = pd.read_csv("data/sample.csv", dtype=str)
    verified = pd.read_csv("data/verified.csv", dtype=str)

    scored = []
    for position in range(len(verified)):
        row = verified.iloc[position]
        status, reason = decide(row)
        scored.append({
            "company_number": row["company_number"],
            "vat_number": row["vat_candidate"],
            "status": status,
            "reason": reason,
            "name_score": round(
                max(similarity(row["hmrc_name"], row["company_name"]),
                    similarity(row["hmrc_name"], row["ch_previous_name"])), 3),
            "company_number_on_site": row["company_number_on_site"],
            "domain": row["domain"],
        })

    scored = pd.DataFrame(scored)

    # Every company in the sample gets a row. NOT_FOUND is a result.
    results = sample[["CompanyNumber", "CompanyName", "stratum"]].rename(
        columns={"CompanyNumber": "company_number", "CompanyName": "company_name"})

    results = results.merge(scored, on="company_number", how="left")
    results["status"] = results["status"].fillna("NOT_FOUND")
    results["reason"] = results["reason"].fillna("no candidate extracted")

    results.to_csv("data/results.csv", index=False)

    print("--- STATUS, all " + str(len(results)) + " companies ---")
    print(results["status"].value_counts())
    print("")
    print("--- STATUS BY STRATUM ---")
    print(pd.crosstab(results["stratum"], results["status"]))
    print("")

    decided = results[results["status"].isin(["CONFIRMED", "MISMATCH"])]
    if len(decided) > 0:
        wrong = (decided["status"] == "MISMATCH").sum()
        print("false positive rate among decided candidates: " +
              str(wrong) + "/" + str(len(decided)) +
              " = " + str(round(100 * wrong / len(decided), 1)) + "%")
        print("(measured on " + str(len(decided)) +
              " candidates - far too few for a confident rate; report the count)")

    print("")
    print(results[results["status"] != "NOT_FOUND"][
        ["company_name", "vat_number", "status", "name_score", "reason"]].to_string(index=False))
    print("")
    print("Saved to data/results.csv")