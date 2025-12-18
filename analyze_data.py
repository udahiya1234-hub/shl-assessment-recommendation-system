import pandas as pd
import os

print("Files in directory:", os.listdir('.'))
print("\n" + "="*80)

xl_file = pd.ExcelFile('Gen_AI Dataset.xlsx')
print('Sheet names:', xl_file.sheet_names)

for sheet in xl_file.sheet_names:
    print(f"\n{'='*80}")
    print(f"Sheet: {sheet}")
    print(f"{'='*80}")
    df = pd.read_excel('Gen_AI Dataset.xlsx', sheet_name=sheet)
    print(f"Shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(f"\nFirst 3 rows:")
    print(df.head(3))
    print(f"\nData types:\n{df.dtypes}")
