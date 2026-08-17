"""
Step 4: prepare the candidates for verification, then hold what HMRC said.

HMRC's open API was withdrawn (see evidence/hmrc_api_probe.txt), so the public web checker is the only route available.
With this few candidates, checking them by hand is faster than automating a government form, and it avoids sending automated traffic at a public service. The decision and its reasoning are in notes.md.

This script does the part a script should do - deduplicate and lay out the
sheet - and leaves the four HMRC columns blank for a human to fill in from
https://www.tax.service.gov.uk/check-vat-number/enter-vat-details

It refuses to overwrite an existing data/verified.csv, because that file contains manual work that cannot be regenerated.

"""

import os
import pandas as pd

OUTPUT = "data/verified.csv"

candidates = pd.read_csv("data/candidates.csv", dtype=str)
sample = pd.read_csv("data/sample.csv", dtype=str)


passing = candidates[candidates["checksum_ok"] == "True"]

print("rows in candidates.csv : " + str(len(candidates)))
print("passing checksum       : " + str(len(passing)))


unique = passing.drop_duplicates(subset=["company_number", "vat_candidate"])

print("distinct company+number: " + str(len(unique)))
print("")

context = sample[[
    "CompanyNumber",
    "RegAddress.PostCode",
    "PreviousName_1.CompanyName",
    "postcode_company_count",
]]

sheet = unique.merge(
    context,
    left_on="company_number",
    right_on="CompanyNumber",
    how="left",
)

sheet = sheet[[
    "company_number",
    "company_name",
    "PreviousName_1.CompanyName",
    "RegAddress.PostCode",
    "postcode_company_count",
    "stratum",
    "domain",
    "vat_candidate",
    "company_number_on_site",
]]

sheet = sheet.rename(columns={
    "PreviousName_1.CompanyName": "ch_previous_name",
    "RegAddress.PostCode": "ch_postcode",
})


sheet["hmrc_valid"] = ""
sheet["hmrc_name"] = ""
sheet["hmrc_postcode"] = ""
sheet["checked_at"] = ""

if os.path.exists(OUTPUT):
    print("!! " + OUTPUT + " already exists and was NOT overwritten.")
    print("   It holds manual work that cannot be regenerated.")
    print("   Delete it yourself if you really want to start over.")
else:
    sheet.to_csv(OUTPUT, index=False)
    print("Wrote " + str(len(sheet)) + " rows to " + OUTPUT)

print("")
print("--- CHECK THESE BY HAND ---")
for position in range(len(sheet)):
    row = sheet.iloc[position]
    print("  " + str(row["vat_candidate"]) +
          "   " + str(row["company_name"])[:40].ljust(42) +
          str(row["domain"]))
print("")
print("At https://www.tax.service.gov.uk/check-vat-number/enter-vat-details")
print("Fill in: hmrc_valid (True/False), hmrc_name, hmrc_postcode, checked_at")