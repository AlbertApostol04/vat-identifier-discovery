import pandas as pd

verified = pd.read_csv("data/verified.csv", dtype=str)

print("coloane:", list(verified.columns))
print("")

for position in range(len(verified)):
    row = verified.iloc[position]
    print("--- rând " + str(position + 1) + " ---")
    for column in verified.columns:
        print("  " + column.ljust(24) + repr(row[column]))
    print("")