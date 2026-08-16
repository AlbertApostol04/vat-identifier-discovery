import requests
import os
from datetime import datetime

os.makedirs("evidence", exist_ok=True)

TEST_VRN = "123456782"

BASE = "https://api.service.hmrc.gov.uk/organisations/vat/check-vat-number/lookup/"

attempts = [
    ("v1_no_accept_header", {}),
    ("v1_explicit_accept_header", {"Accept": "application/vnd.hmrc.1.0+json"}),
    ("v2_accept_header", {"Accept": "application/vnd.hmrc.2.0+json"}),
]

lines = []
lines.append("HMRC VAT check API probe")
lines.append("run at: " + datetime.now().isoformat())
lines.append("test VRN: " + TEST_VRN + "  (checksum-valid, not a real company)")
lines.append("")

for name, headers in attempts:
    url = BASE + TEST_VRN
    lines.append("=" * 60)
    lines.append("attempt: " + name)
    lines.append("GET " + url)
    lines.append("request headers: " + str(headers))

    try:
        response = requests.get(url, headers=headers, timeout=15)
        lines.append("status code: " + str(response.status_code))
        lines.append("response headers: " + str(dict(response.headers)))
        lines.append("body:")
        lines.append(response.text)
    except Exception as error:
        lines.append("EXCEPTION: " + str(error))

    lines.append("")

report = "\n".join(lines)
print(report)

with open("evidence/hmrc_api_probe.txt", "w", encoding="utf-8") as f:
    f.write(report)

print("")
print("Saved to evidence/hmrc_api_probe.txt")
