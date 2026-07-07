#!/usr/bin/env python3
"""Convert binary spreadsheet files (xls, xlsx, xlsb) to CSV."""

import os
import csv
import sys

RAW_DIR = '/opt/data/kiwisaver-data/raw/fma-csvs'

def convert_xlsx(path):
    """Convert .xlsx file to CSV using openpyxl."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    return rows

def convert_xls(path):
    """Convert .xls file to CSV using xlrd."""
    import xlrd
    wb = xlrd.open_workbook(path)
    ws = wb.sheet_by_index(0)
    rows = []
    for row_idx in range(ws.nrows):
        rows.append([ws.cell_value(row_idx, col_idx) for col_idx in range(ws.ncols)])
    return rows

def convert_xlsb(path):
    """Convert .xlsb file to CSV using pyxlsb."""
    from pyxlsb import open_workbook
    with open_workbook(path) as wb:
        sheet_name = wb.sheets[0]
        with wb.get_sheet(sheet_name) as ws:
            rows = []
            for row in ws.rows():
                rows.append([c.v if c.v is not None else '' for c in row])
    return rows

def write_csv(rows, outpath):
    """Write rows to CSV."""
    with open(outpath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        for row in rows:
            cleaned = []
            for cell in row:
                if cell is None:
                    cleaned.append('')
                else:
                    cleaned.append(str(cell))
            writer.writerow(cleaned)
    print(f"  Wrote {len(rows)} rows to {outpath}")

def main():
    binary_files = []
    for f in os.listdir(RAW_DIR):
        if f.endswith('.xls') or f.endswith('.xlsx') or f.endswith('.xlsb'):
            binary_files.append(f)
    
    binary_files.sort()
    print(f"Found {len(binary_files)} binary files to convert:")
    for f in binary_files:
        print(f"  - {f}")
    
    for filename in binary_files:
        path = os.path.join(RAW_DIR, filename)
        outpath = os.path.join(RAW_DIR, f"{filename}.converted.csv")
        
        if os.path.exists(outpath):
            print(f"\nSkipping {filename} - output already exists")
            continue
        
        print(f"\nConverting: {filename}")
        try:
            if filename.endswith('.xlsx'):
                rows = convert_xlsx(path)
            elif filename.endswith('.xlsb'):
                rows = convert_xlsb(path)
            elif filename.endswith('.xls'):
                rows = convert_xls(path)
            else:
                print(f"  Unknown format: {filename}")
                continue
            
            write_csv(rows, outpath)
        except Exception as e:
            print(f"  ERROR converting {filename}: {e}")
            # Write error info
            with open(outpath.replace('.converted.csv', '.error.txt'), 'w') as ef:
                ef.write(f"Conversion failed: {e}\n")

if __name__ == '__main__':
    main()
