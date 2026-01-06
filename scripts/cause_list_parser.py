#!/usr/bin/env python3
"""
Simplified Cause List PDF Parser
Based on test20.py with Supabase integration
"""

import os
import re
from datetime import datetime
from supabase import create_client, Client
from pypdf import PdfReader
from io import BytesIO
import logging
import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
CAUSE_LIST_URL = "https://judiciary.karnataka.gov.in/pdfs/consolidatedCauselist/blrconsolidation.pdf"
# Constants for anchor-based parsing
CASE_TYPES_LIST = [
    r"MFA\.CROB", r"MSA\.CROB", r"RFA\.CROB", r"RSA\.CROB", r"WA\.CROB", r"ITA\.CROB", r"OSA\.CROB",
    r"COM\.APLN", r"COMAP\.CR", r"MISC\.CRL", r"MISC\.CVL", r"RERA\.CRB", r"CC\(CIA\)", r"CP\.KLRA", 
    r"PROB\.CP", r"CRL\.CCC", r"CRL\.RP", r"CRL\.RC", r"MISC\.W", r"MISC\.P", r"RERA\.A", r"AP\.EFA", 
    r"AP\.IM", r"COM\.OS", r"COM\.S", r"COMAP", r"COMPA", r"CRL\.A", r"CRL\.P", r"EX\.FA", r"EX\.SA", 
    r"HRRP", r"ITRC", r"LRRP", r"LTRP", r"SCLAP", r"STRP", r"TAET", r"WPHC", r"WPCP", r"CSTA", r"CROB", 
    r"MISC", r"CCC", r"CEA", r"CMP", r"COA", r"COP", r"CRA", r"CRC", r"CRP", r"GTA", r"ITA", r"MFA", 
    r"MSA", r"OLR", r"OSA", r"RFA", r"TOS", r"TRC", r"WTA", r"AC", r"CA", r"CP", r"OS", r"RA", r"RP", 
    r"WA", r"WP", r"SA", r"S"
]
CASE_TYPES_REGEX = "|".join(CASE_TYPES_LIST)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',    handlers=[
        logging.FileHandler('app.log'),  # Creates log file
        logging.StreamHandler()  # Also logs to console
    ])


def http_worker_call_to_supabase():
    try:
        url: str = "https://gthnjueqoufdtwtzjcxg.supabase.co/functions/v1/http-worker"
        supabase: Client = create_client(url, SUPABASE_KEY)
        supabase.functions._client.timeout = httpx.Timeout(30.0)
        response = supabase.functions.invoke(
            "http-worker",
            invoke_options={
                "body": {"targetUrl": CAUSE_LIST_URL},
                "method": "POST",
                "headers": {"x-region": "ap-south-1"}
            }
        )
        return response
    except Exception as e:
        logging.error(f"HTTP worker exception: {e}")
        return None


def download_pdf(url):
    """Download PDF from URL"""
    try:
        data = http_worker_call_to_supabase()
        if data:
            logging.info("PDF downloaded successfully")
            return BytesIO(data)
        return None
    except Exception as e:
        logging.error(f"PDF download error: {e}")
        return None

def parse_judges(judge_line):
    """Parse judge names from BEFORE section"""
    # Remove 'BEFORE' prefix
    text = re.sub(r'^BEFORE\s+', '', judge_line.strip(), flags=re.IGNORECASE)
    # Remove all instances of 'THE HON'BLE' (handles both single and double judge lines)
    text = re.sub(r'THE\s+HON\'BLE\s+', '', text, flags=re.IGNORECASE)
    # Clean up extra whitespace and newlines
    text = " ".join(text.split()).strip()

    return text if text else "N/A"


def parse_case_details(raw_case_id):
    """Extract Case Type, Case No, and Details from case identifier"""
    text = " ".join(raw_case_id.split()).strip()
    case_type, case_no, case_details = "N/A", "N/A", "N/A"

    # Extract case type from parentheses at end
    if text.endswith(')'):
        depth = 0
        split_index = -1
        for i in range(len(text) - 1, -1, -1):
            if text[i] == ')': 
                depth += 1
            elif text[i] == '(': 
                depth -= 1
            if depth == 0:
                split_index = i
                break
        if split_index != -1:
            case_type = text[split_index + 1 : -1].strip()
            text = text[:split_index].strip()

    # Extract case number
    no_match = re.search(r"([A-Z.]+\s+\d+[\d/\\]+)", text)
    if no_match:
        case_no = no_match.group(1).strip()
        case_details = text.replace(case_no, "").strip() or "N/A"
    else:
        case_details = text or "N/A"
    
    return case_no, case_type, case_details


def extract_advocate(text):
    """Extract advocate name from petitioner/respondent text (last mixed-case line)"""
    if not text:
        return None
    
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # Look for mixed-case lines (advocates are typically not all uppercase)
    for line in reversed(lines):
        if not line or len(line) < 3:
            continue
        
        # Skip all-uppercase lines (party names)
        if line.isupper():
            continue
        
        # Skip common keywords
        skip_keywords = ['AND OTHERS', 'OTHERS', 'NOT FILED', 'SD', 'VK']
        if any(keyword in line.upper() for keyword in skip_keywords):
            continue
        
        # Found advocate
        return line.strip()
    
    return None


def parse_pdf_to_cases(pdf_file):
    """Parse PDF and extract all cases"""
    reader = PdfReader(pdf_file)
    full_document_text = []
    
    # Extract all text
    for page in reader.pages:
        page_text = page.extract_text()
        # Clean footer
        page_text = re.sub(r"Website:https://judiciary\.karnataka\.gov\.in.*?\n", "", page_text)
        page_text = re.sub(r"Page \d+ of \d+ \d+", "", page_text)
        full_document_text.append(page_text)

    cleaned_text = "\n".join(full_document_text)
    # Pre-clean: Remove footers that break multi-page cases and noise markers
    cleaned_text = re.sub(r"Website:https://judiciary\.karnataka\.gov\.in.*?Page \d+ of \d+.*?\n", "", cleaned_text)
    cleaned_text = re.sub(r"Connected With", "", cleaned_text, flags=re.IGNORECASE)
    
    # State tracking
    current_hall, current_cause_list, current_judges = "N/A", "N/A", "N/A"
    all_cases = []
    date_str = datetime.now().strftime('%Y-%m-%d')

    # Combined pattern updated with Case Type anchors and decimal serial numbers
    combined_pattern = re.compile(
        r"(?:COURT\s+HALL\s+NO\s*:\s*(\d+))|" +
        r"(?:CAUSE\s+LIST\s+NO\.\s*(\d+))|" +
        r"(BEFORE\s+(?:THE\s+HON'BLE|REGISTRAR).*?(?=\(To get))|" +
        r"(?:^\s*(\d+(?:\.\d+)?)\s+((?:%s)\s+\d+.*?)\s+PET:\s*(.+?)\s+RES:\s*(.+?)" % CASE_TYPES_REGEX +
        r"(?=\n\s*(?:\d+(?:\.\d+)?\s+(?:%s)|CAUSE|BEFORE|---END---|$)))" % CASE_TYPES_REGEX,
        re.MULTILINE | re.IGNORECASE | re.DOTALL
    )
    matches = combined_pattern.findall(cleaned_text)
    
    for match in matches:
        hall, cause_no, judge_line, sno, raw_case_id, pet, res = match

        if hall:
            current_hall = hall.strip()
            logging.info(f"Processing Court Hall {current_hall}")
        elif cause_no:
            current_cause_list = cause_no.strip()
        elif judge_line:
            current_judges = parse_judges(judge_line)
            logging.info(f"  Judges: {current_judges}")
        elif sno:
            # Clean RES if any footer hall info was captured
            res = re.sub(r"COURT\s+HALL\s+NO\s*:\s*\d+", "", res, flags=re.IGNORECASE).strip()
            # Parse case details
            case_no, case_type, case_details = parse_case_details(raw_case_id)
            
            # Extract advocates TODO
            #pet_adv = extract_advocate(pet)
            #res_adv = extract_advocate(res)
            
            case_record = {
                'date': date_str,
                'court_hall': int(current_hall) if current_hall != "N/A" else None,
                'list_number': int(current_cause_list) if current_cause_list != "N/A" else None,
                'sl_no': float(sno), # Float supports 44.1
                'case_number': case_no,
                'case_type': case_type,
                'case_details': case_details if case_details != "N/A" else None,
                'judges': current_judges if current_judges != "N/A" else None,
                'petitioner_adv': pet,
                'respondent_adv': res
            }
            
            all_cases.append(case_record)
            logging.debug(f"  [{sno}] {case_no}")

    logging.info(f"Total cases parsed: {len(all_cases)}")
    return all_cases


def insert_to_supabase(cases):
    """Insert parsed cases into Supabase using RPC"""
    if not cases:
        logging.warning("No cases to insert")
        return
    
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Delete all existing rows from cause_list table (daily fresh start)
        logging.info("Clearing cause_list table for today's data...")
        supabase.table('cause_list').delete().neq('case_number', '').execute()
        logging.info("Previous cause_list data cleared")

        
        logging.info(f"Calling RPC function with {len(cases)} cases...")
        result = supabase.rpc('insert_cause_list_batch', {'cases_data': cases}).execute()
        
        if result.data and len(result.data) > 0:
            stats = result.data[0]
            inserted = stats.get('inserted_count', 0)
            updated = stats.get('updated_count', 0)
            
            logging.info(f"Database operation completed:")
            logging.info(f"  - Inserted: {inserted} new cases")
            logging.info(f"  - Updated: {updated} existing cases")
            logging.info(f"  - Total processed: {inserted + updated}")
        else:
            logging.info(f"Processed {len(cases)} cases")
        
        # Log summary
        from collections import defaultdict
        hall_counts = defaultdict(int)
        
        for case in cases:
            if case['court_hall']:
                hall_counts[case['court_hall']] += 1
        
        logging.info("\nCases by court hall:")
        for hall, count in sorted(hall_counts.items()):
            logging.info(f"  Court Hall {hall}: {count} cases")
        
    except Exception as e:
        logging.error(f"Supabase RPC error: {e}")


def main():
    """Main execution"""
    logging.info("="*60)
    logging.info("Starting Simplified Cause List Parser")
    logging.info("="*60)
    
    pdf_file = download_pdf(CAUSE_LIST_URL)
    if not pdf_file:
        logging.error("Failed to download PDF")
        return
    
    cases = parse_pdf_to_cases(pdf_file)
   
    if cases:
        logging.info(f"\nSuccessfully parsed {len(cases)} total cases")
        insert_to_supabase(cases)
        logging.info("\nCause list parsing completed successfully")
    else:
        logging.error("No cases were parsed from PDF")


if __name__ == "__main__":
    main()
