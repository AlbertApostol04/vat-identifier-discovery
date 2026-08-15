""" 00b lists column positions was added after a parsing bug returned data from the wrong columns without raising an error. """
import pandas as pd

CSV_PATH = r"D:\OneDrive - unibuc.ro\Desktop\vat-identifier-discovery\BasicCompanyDataAsOneFile-2026-08-01\BasicCompanyDataAsOneFile-2026-08-01.csv"


sample = pd.read_csv(CSV_PATH, nrows=3, dtype=str)

print("Number of columns: " + str(len(sample.columns)))
print("")

position = 0
for name in sample.columns:
    value = str(sample[name].iloc[0])
    print(str(position) + "  " + repr(name) + "  ->  " + repr(value))
    position = position + 1

