import pandas as pd
import sys

file_path = 'utic_cctv_list.xls'
target_id = 'D1000740'

try:
    # Try reading as Excel (it might be .xls or .xlsx)
    # The 'file' command output will help, but pandas usually handles it.
    # However, sometimes these gov sites serve HTML tables as .xls.
    # We'll try standard read_excel first.
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"Standard read_excel failed: {e}")
        # Try reading as HTML if it's actually an HTML table
        try:
             dfs = pd.read_html(file_path)
             if dfs:
                 df = dfs[0]
             else:
                 print("No tables found in HTML.")
                 sys.exit(1)
        except Exception as e2:
            print(f"read_html failed: {e2}")
            sys.exit(1)

    print("Columns:", df.columns.tolist())
    
    # Search for the ID
    # We'll look in all columns just in case
    found = False
    for col in df.columns:
        # Convert to string to ensure we can search
        mask = df[col].astype(str).str.contains(target_id, na=False)
        if mask.any():
            print(f"Found {target_id} in column '{col}'!")
            print(df[mask])
            found = True
            
            # If found, print the whole row to see if there's a URL
            row = df[mask].iloc[0]
            print("\nRow Data:")
            for c in df.columns:
                print(f"{c}: {row[c]}")
            break
            
    if not found:
        print(f"ID {target_id} not found in the file.")
        print(f"Total rows: {len(df)}")
        print(f"Sample data:\n{df.head()}")

except Exception as e:
    print(f"An error occurred: {e}")
