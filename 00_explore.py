import pandas as pd
from collections import Counter
import os

os.makedirs("data", exist_ok=True)

CSV_PATH = r"D:\OneDrive - unibuc.ro\Desktop\vat-identifier-discovery\BasicCompanyDataAsOneFile-2026-08-01\BasicCompanyDataAsOneFile-2026-08-01.csv"

# sample = pd.read_csv(CSV_PATH, nrows=5, dtype=str, skipinitialspace= True )
#
# print("Column names:")
# for name in sample.columns:
#     print(" ["+name+"] ")

COLUMNS = ["CompanyNumber", "Accounts.AccountCategory", "RegAddress.PostCode"]

reader = pd.read_csv(
    CSV_PATH,
    usecols=COLUMNS,
    dtype=str,
    skipinitialspace=True,
    chunksize=100000
)

total_rows = 0

account_counts = Counter()

postcode_counts = Counter()

for chunk in reader:
    total_rows = total_rows + len(chunk)
    # print("read so far:" + str(total_rows))
    account_counts.update(chunk["Accounts.AccountCategory"].dropna())
    postcode_counts.update(chunk["RegAddress.PostCode"].dropna())

print("Total rows:" + str(total_rows))

print("")

print("---ACCOUNT CATEGORY---")
for name, count in account_counts.most_common():
    print("  " + str(count) + "  " + name)

print("")
print("---TOP 20 POSTCODES---")
for code, count in postcode_counts.most_common(20):
    print("  " + str(count) + "  " + code)

postcode_table = pd.DataFrame(
    postcode_counts.most_common(),
    columns=["postcode", "company_count"]
)

postcode_table.to_csv("data/postcode_frequency.csv", index=False)

print("")
print("Saved " + str(len(postcode_table)) + " postcodes to data/postcode_frequency.csv")


