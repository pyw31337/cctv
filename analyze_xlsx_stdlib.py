import zipfile
import xml.etree.ElementTree as ET
import os

file_path = 'utic_cctv_list.xls'
target_id = 'D1000740'

def read_xlsx_std_lib(path):
    print(f"Reading {path} using standard library zipfile+xml...")
    try:
        with zipfile.ZipFile(path, 'r') as z:
            # 1. Parse Shared Strings
            shared_strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                with z.open('xl/sharedStrings.xml') as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    # namespace usually: http://schemas.openxmlformats.org/spreadsheetml/2006/main
                    # but we can just ignore namespaces for simple extraction or handle them
                    ns = {'appt': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    for t in root.findall('.//appt:t', ns):
                        shared_strings.append(t.text)
            
            print(f"Found {len(shared_strings)} shared strings.")

            # 2. Parse Sheet 1
            if 'xl/worksheets/sheet1.xml' in z.namelist():
                with z.open('xl/worksheets/sheet1.xml') as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    ns = {'appt': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    
                    rows = []
                    for row in root.findall('.//appt:row', ns):
                        row_data = []
                        for cell in row.findall('.//appt:c', ns):
                            t = cell.get('t')
                            val = cell.find('appt:v', ns)
                            if val is not None:
                                v = val.text
                                if t == 's': # shared string
                                    idx = int(v)
                                    if idx < len(shared_strings):
                                        row_data.append(shared_strings[idx])
                                    else:
                                        row_data.append(f"STR#{idx}")
                                else:
                                    row_data.append(v)
                            else:
                                # sometimes inline strings
                                ist = cell.find('appt:is/appt:t', ns)
                                if ist is not None:
                                    row_data.append(ist.text)
                        
                        rows.append(row_data)
                    
                    return rows
            else:
                print("Sheet1 not found.")
                return []

    except Exception as e:
        print(f"Error extracting xlsx: {e}")
        return []

# Run the extraction
rows = read_xlsx_std_lib(file_path)

if not rows:
    print("No rows extracted.")
else:
    print(f"Extracted {len(rows)} rows.")
    
    # Analysis: Count by CENTERNAME (index 3 based on header)
    center_counts = {}
    
    # Skip header
    data_rows = rows[1:]
    
    for row in data_rows:
        if len(row) > 3:
            center = row[3]
            center_counts[center] = center_counts.get(center, 0) + 1
            
    print("\n--- CCTV Distribution by Center ---")
    sorted_centers = sorted(center_counts.items(), key=lambda x: x[1], reverse=True)
    for center, count in sorted_centers:
        print(f"{center}: {count}")
        
    print(f"\nTotal CCTVs in file: {len(data_rows)}")

