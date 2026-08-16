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