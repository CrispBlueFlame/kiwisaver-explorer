#!/usr/bin/env python3
"""
Extract tables/data from FMA KiwiSaver Annual Report PDFs (2011-2025).
Uses PyMuPDF (fitz) for text extraction and pdfplumber for table extraction.
"""

import json
import os
import re
import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

PDF_DIR = '/opt/data/kiwisaver-data/raw/fma-reports'
OUT_DIR = '/opt/data/kiwisaver-data/extracted'


def extract_pdf_pymupdf(filepath):
    """Extract text from PDF using PyMuPDF."""
    doc = fitz.open(filepath)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text()
        pages.append({
            'page_num': i + 1,
            'text': text,
        })
    doc.close()
    return pages


def extract_tables_pdfplumber(filepath):
    """Try to extract tables from PDF using pdfplumber."""
    if pdfplumber is None:
        return None, "pdfplumber not available"
    
    tables = []
    try:
        with pdfplumber.open(filepath) as pdf:
            for i, page in enumerate(pdf.pages):
                page_tables = page.extract_tables()
                if page_tables:
                    for t_idx, table in enumerate(page_tables):
                        tables.append({
                            'page_num': i + 1,
                            'table_index': t_idx,
                            'data': table,
                        })
        return tables, None
    except Exception as e:
        return None, str(e)


def parse_report_metadata(filename):
    """Extract year from filename."""
    year_match = re.search(r'(\d{4})', filename)
    if year_match:
        return int(year_match.group(1))
    return None


def find_members_fum_from_text(pages):
    """Search through extracted text for members count, FUM, fee data."""
    results = {
        'total_members': None,
        'total_fum': None,
        'total_fees': None,
        'avg_fees_per_member': None,
        'num_providers': None,
        'notes': [],
    }
    
    combined_text = '\n'.join([p['text'] for p in pages])
    
    # Search for total members - various patterns
    patterns_members = [
        r'([\d,]+)\s*KiwiSaver\s*members',
        r'total\s*(?:of)?\s*([\d,]+)\s*members?',
        r'members?\s*(?:of|:)?\s*([\d,]+)',
        r'([\d,]+)\s*members?\s*(?:in|enrolled|registered)',
        r'approximately\s*([\d,]+)\s*members?',
    ]
    for pattern in patterns_members:
        matches = re.findall(pattern, combined_text, re.IGNORECASE)
        if matches:
            # Try to get the largest number (most likely aggregate)
            nums = []
            for m in matches:
                try:
                    nums.append(int(m.replace(',', '')))
                except ValueError:
                    pass
            if nums:
                results['total_members'] = max(nums)
                break
    
    # Search for total FUM
    patterns_fum = [
        r'(?:total\s+)?(?:funds?\s+under\s+management|fum|net\s+assets)\s*(?:of|:)?\s*\$?([\d,]+(?:\.[\d]+)?)\s*(?:billion|million|bn|m|b)',
        r'\$?([\d,]+(?:\.[\d]+)?)\s*(?:billion|million)\s*(?:in\s+)?(?:funds?\s+under\s+management|fum|net\s+assets)',
        r'(?:total|aggregate)\s*(?:fund|scheme)\s*(?:value|assets)\s*(?:of|:)?\s*\$?([\d,]+(?:\.[\d]+)?)\s*(?:billion|million)',
    ]
    for pattern in patterns_fum:
        matches = re.findall(pattern, combined_text, re.IGNORECASE)
        if matches:
            results['total_fum'] = matches[0]
            # Try to capture units
            unit_match = re.search(rf'{re.escape(matches[0])}\s*(billion|million|bn|m|b)', combined_text, re.IGNORECASE)
            if unit_match:
                results['total_fum_unit'] = unit_match.group(1)
            break
    
    # Search for number of providers
    patterns_providers = [
        r'([\d]+)\s*(?:KiwiSaver\s+)?(?:schemes?|providers?)',
        r'(?:schemes?|providers?)\s*(?:operating|offering|available|listed)\s*(?:of|:)?\s*([\d]+)',
    ]
    for pattern in patterns_providers:
        matches = re.findall(pattern, combined_text, re.IGNORECASE)
        if matches:
            nums = []
            for m in matches:
                try:
                    n = int(m)
                    if 5 < n < 100:  # reasonable provider count
                        nums.append(n)
                except ValueError:
                    pass
            if nums:
                results['num_providers'] = max(nums)
                break
    
    # Search for fee data
    patterns_fees = [
        r'(?:total|aggregate)\s*(?:annual\s+)?(?:fees|charges?)\s*(?:of|:)?\s*\$?([\d,]+(?:\.[\d]+)?)\s*(?:million|billion)',
        r'(?:average|avg\.?)\s*(?:fee|charge|cost)\s*(?:per|for\s+each)\s*member\s*\$?([\d,]+(?:\.[\d]+)?)',
    ]
    for pattern in patterns_fees:
        matches = re.findall(pattern, combined_text, re.IGNORECASE)
        if matches:
            if 'fee' in pattern and 'per' in pattern:
                results['avg_fees_per_member'] = matches[0]
            else:
                results['total_fees'] = matches[0]
    
    # If nothing was found, flag for manual review
    if results['total_members'] is None and results['total_fum'] is None:
        results['notes'].append('Could not auto-extract key metrics - needs manual review')
    
    return results


def process_pdf(filepath):
    """Process a single PDF file."""
    filename = os.path.basename(filepath)
    year = parse_report_metadata(filename)
    
    print(f"Processing: {filename} (year ~{year})")
    
    result = {
        'filename': filename,
        'year': year,
        'extraction_method': None,
        'pages_count': 0,
        'table_count': 0,
        'extracted_text_chars': 0,
        'metrics': {},
        'tables': [],
        'sample_text': '',
        'needs_manual_review': False,
    }
    
    # Extract text with PyMuPDF
    if fitz:
        try:
            pages = extract_pdf_pymupdf(filepath)
            result['pages_count'] = len(pages)
            result['extraction_method'] = 'pymupdf'
            result['extracted_text_chars'] = sum(len(p['text']) for p in pages)
            
            # Save sample text (first page)
            if pages:
                result['sample_text'] = pages[0]['text'][:2000]
            
            # Try to extract metrics from text
            metrics = find_members_fum_from_text(pages)
            result['metrics'] = metrics
            if metrics.get('notes'):
                result['needs_manual_review'] = True
            
            # Try table extraction with pdfplumber
            tables, error = extract_tables_pdfplumber(filepath)
            if tables:
                result['table_count'] = len(tables)
                result['tables'] = tables[:20]  # limit to first 20 tables
                result['extraction_method'] = 'pymupdf+pdfplumber'
            elif error:
                result['table_error'] = error
            
        except Exception as e:
            print(f"  ERROR with PyMuPDF: {e}")
            result['needs_manual_review'] = True
            result['extraction_error'] = str(e)
    else:
        result['needs_manual_review'] = True
        result['extraction_error'] = 'PyMuPDF not available'
    
    return result


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    
    pdf_files = sorted([f for f in os.listdir(PDF_DIR) if f.endswith('.pdf')])
    print(f"Found {len(pdf_files)} PDF files")
    
    all_reports = []
    
    for filename in pdf_files:
        filepath = os.path.join(PDF_DIR, filename)
        try:
            result = process_pdf(filepath)
            all_reports.append(result)
            
            # Save individual report
            year_str = str(result['year']) if result['year'] else filename[:20]
            out_path = os.path.join(OUT_DIR, f'fma_report_{year_str}.json')
            # Omit large tables from individual file to keep it manageable
            report_save = {k: v for k, v in result.items() if k != 'tables'}
            report_save['table_count'] = result['table_count']
            if result.get('tables'):
                report_save['tables_summary'] = [
                    {'page': t['page_num'], 'rows': len(t['data']), 'cols': max(len(r) for r in t['data']) if t['data'] else 0}
                    for t in result['tables'][:10]
                ]
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(report_save, f, indent=2, default=str)
            print(f"  Saved to {out_path}")
            print(f"  Pages: {result['pages_count']}, Tables: {result['table_count']}, Chars: {result['extracted_text_chars']}")
            if result['needs_manual_review']:
                print(f"  ⚠ Needs manual review")
            
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    # Save combined
    combined_path = os.path.join(OUT_DIR, 'fma_reports_combined.json')
    # Summarize for combined file
    combined_summary = []
    for r in all_reports:
        combined_summary.append({
            'filename': r['filename'],
            'year': r['year'],
            'pages_count': r['pages_count'],
            'table_count': r['table_count'],
            'extracted_text_chars': r['extracted_text_chars'],
            'metrics': r['metrics'],
            'needs_manual_review': r['needs_manual_review'],
            'extraction_error': r.get('extraction_error'),
        })
    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump(combined_summary, f, indent=2, default=str)
    print(f"\nSaved combined summary ({len(all_reports)} reports) to {combined_path}")
    
    # Print summary
    print(f"\n=== PDF EXTRACTION SUMMARY ===")
    for r in all_reports:
        status = '⚠ Manual review needed' if r['needs_manual_review'] else '✅ Auto-extracted'
        print(f"  {r['filename']}: {r['pages_count']} pages, {r['table_count']} tables - {status}")
        m = r.get('metrics', {})
        if m.get('total_members'):
            print(f"    Members: {m['total_members']}, FUM: {m.get('total_fum', 'N/A')}, Providers: {m.get('num_providers', 'N/A')}")


if __name__ == '__main__':
    main()
