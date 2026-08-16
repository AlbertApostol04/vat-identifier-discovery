import pandas as pd
import random
import os
from config import CSV_PATH, CHUNK_SIZE

os.makedirs("data", exist_ok=True)

SAMPLE_SIZE = 75
NOT_TRADING = ["DORMANT", "NO ACCOUNTS FILED"]

pass1_reader = pd.read_csv(
    CSV_PATH,
    usecols=["CompanyNumber", "CompanyStatus", "Accounts.AccountCategory"],
    dtype=str,
    skipinitialspace=True,
    chunksize=100000,
)

pool_all = []
pool_trading = []

for chunk in pass1_reader:
    active = chunk[chunk["CompanyStatus"] == "Active"]
    pool_all.extend(active["CompanyNumber"].tolist())

    trading = active[~active["Accounts.AccountCategory"].isin(NOT_TRADING)]
    pool_trading.extend(trading["CompanyNumber"].tolist())

print("pool_all:     " + str(len(pool_all)))
print("pool_trading: " + str(len(pool_trading)))

random.seed(42)
chosen_all = random.sample(pool_all, SAMPLE_SIZE)
chosen_trading = random.sample(pool_trading, SAMPLE_SIZE)

overlap = set(chosen_all) & set(chosen_trading)
print("overlap between strata: " + str(len(overlap)))

chosen_set = set(chosen_all) | set(chosen_trading)

SAMPLE_COLUMNS = [
    "CompanyName",
    "CompanyNumber",
    "RegAddress.AddressLine1",
    "RegAddress.PostTown",
    "RegAddress.PostCode",
    "CompanyStatus",
    "IncorporationDate",
    "Accounts.AccountCategory",
    "SICCode.SicText_1",
    "PreviousName_1.CompanyName",
]

pass2_reader = pd.read_csv(
    CSV_PATH,
    usecols=SAMPLE_COLUMNS,
    dtype=str,
    skipinitialspace=True,
    chunksize=CHUNK_SIZE,
)

pieces = []
for chunk in pass2_reader:
    keep = chunk[chunk["CompanyNumber"].isin(chosen_set)]
    if len(keep) > 0:
        pieces.append(keep)

sample = pd.concat(pieces)
print("rows collected: " + str(len(sample)))

all_set = set(chosen_all)
sample["stratum"] = "trading"
sample.loc[sample["CompanyNumber"].isin(all_set), "stratum"] = "all"
print(sample["stratum"].value_counts())

freq = pd.read_csv("data/postcode_frequency.csv", dtype={"postcode": str})

sample = sample.merge(
    freq,
    left_on="RegAddress.PostCode",
    right_on="postcode",
    how="left",
)
sample = sample.drop(columns=["postcode"])
sample = sample.rename(columns={"company_count": "postcode_company_count"})

sample.to_csv("data/sample.csv", index=False)
print("Saved " + str(len(sample)) + " companies to data/sample.csv")

print("")
print(sample["postcode_company_count"].describe())
