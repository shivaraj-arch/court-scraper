#!/usr/bin/env python3
"""
Simplified Cause List PDF Parser
Based on test20.py with Supabase integration
"""

import os
import re
from datetime import datetime, timezone, timedelta
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
    r"AC", r"AP\.EFA", r"AP\.IM", r"CA", r"CC\(CIA\)", r"CCC", r"CEA", r"CMP", r"COA",
    r"COM\.APLN", r"COM\.OS", r"COM\.S", r"COMAP", r"COMAP\.CR", r"COMPA", r"COP", r"CP",
    r"CP\.KLRA", r"CRA", r"CRC", r"CRL\.A", r"CRL\.CCC", r"CRL\.P", r"CRL\.RC", r"CRL\.RP",
    r"CROB", r"CRP", r"CSTA", r"EX\.FA", r"EX\.SA", r"GTA", r"HRRP", r"ITA", r"ITA\.CROB",
    r"ITRC", r"LRRP", r"LTRP", r"MFA", r"MFA\.CROB", r"MISC\.CRL", r"MISC\.CVL", r"MISC\.P",
    r"MISC\.W", r"MSA", r"MSA\.CROB", r"OLR", r"OS", r"OSA", r"OSA\.CROB", r"PROB\.CP",
    r"RA", r"RERA\.A", r"RERA\.CRB", r"RFA", r"RFA\.CROB", r"RP", r"RPFC", r"RSA",
    r"RSA\.CROB", r"SCLAP", r"STA", r"STRP", r"TAET", r"TOS", r"TRC", r"WA", r"WA\.CROB",
    r"WP", r"WPCP", r"WPHC", r"WTA", r"EP"
] #EP added as its not present in casetypes.pdf after 28 its 30
CASE_TYPES_REGEX = "|".join(CASE_TYPES_LIST)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',    handlers=[
        logging.FileHandler('app.log'),  # Creates log file
        logging.StreamHandler()  # Also logs to console
    ])

def extract_pdf_date(text):
    """Extracts date from 'ON THE DAY OF ... 23rd Day Of January 2026'"""
    pattern = re.compile(
        r"ON THE DAY OF .*? THE (\d+)(?:st|nd|rd|th)?\s+Day\s+Of\s+([A-Za-z]+)\s+(\d{4})", 
        re.IGNORECASE
    )
    match = pattern.search(text)
    if match:
        day, month, year = match.groups()
        date_str = f"{day} {month} {year}"
        try:
            return datetime.strptime(date_str, "%d %B %Y").strftime("%Y-%m-%d")
        except: return None
    return None

def toggle_system_switch(supabase, status, reason=""):
    """Turns the global scraping/EOD switch ON or OFF"""
    supabase.table('system_config').update({
        'is_active': status,
        'reason': reason,
        'last_updated': datetime.now().isoformat()
    }).eq('key', 'master_kill_switch').execute()

def is_date_already_processed(supabase, pdf_date):
    """Checks if this specific date is already in our history"""
    result = supabase.table('daily_summary').select('date').eq('date', pdf_date).execute()
    return len(result.data) > 0

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
    # check if the date is not the previous working day's!
    pdf_date = extract_pdf_date(cleaned_text)
    
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        # Get today's date in IST (India Standard Time)
        ist_now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        today_date = ist_now.strftime('%Y-%m-%d')

        if pdf_date:
            logging.info(f"PDF Date found: {pdf_date} | Today's Date (IST): {today_date}")
            
            # Condition 1: Mismatch (Old or Future date)
            if pdf_date != today_date:
                reason = f"Date mismatch: PDF ({pdf_date}) is not Today ({today_date}). likely holiday/early preparation."
                logging.warning(reason)
                toggle_system_switch(supabase, False, reason)
                return # Exit script
                
            # Condition 2: Already processed (Idempotency check)
            elif is_date_already_processed(supabase, pdf_date):
                logging.warning(f"Cause list for {pdf_date} already exists in database. Turning system OFF.")
                toggle_system_switch(supabase, False, f"Date {pdf_date} already processed.")
                return # Exit script
                
            # Condition 3: Match and New
            else:
                logging.info("VALID DATE DETECTED. Turning system ON.")
                toggle_system_switch(supabase, True, f"Processing Cause List for {pdf_date}")
                
    except Exception as e:
        logging.error(f"Supabase date validation error: {e}")

    # State tracking
    current_hall, current_cause_list, current_judges = "N/A", "N/A", "N/A"
    all_cases = []
    date_str = datetime.now().strftime('%Y-%m-%d')

    # Combined pattern updated with Case Type anchors and decimal serial numbers
    combined_pattern = re.compile(
        r"(?:COURT\s+HALL\s+NO\s*[:]\s*(\w+))|" +  #Capture \w+ to support 2A
        r"(?:CAUSE\s+LIST\s+NO\.\s*(.*?)\n)|" +    
        r"(BEFORE\s+(?:THE\s+HON'BLE\s+(?:(?:DR\.|MRS\.|MS\.|CHIEF|[A-Z\.]{2,10})\s+)?JUSTICE|REGISTRAR).*?(?=\(To get))|" +
        r"(?:^\s*(\d+(?:\.\d+)?)\s+((?:%s)\s+\d+.*?)\s+PET:\s*(.+?)\s+RES:\s*(.+?)" % CASE_TYPES_REGEX +
        r"(?=\n\s*(?:\d+(?:\.\d+)?\s+(?:%s)|CAUSE|BEFORE|---END---|$)))" % CASE_TYPES_REGEX,
        re.MULTILINE | re.IGNORECASE | re.DOTALL
    )
    matches = combined_pattern.findall(cleaned_text)
    # State tracking
    current_hall, current_cause_list, current_judges = "0", "0", "N/A"
    orphans = []  # List for Hall-less cases found at the start of a page
    all_cases = []
 
    for match in matches:
        hall, cause_no, judge_line, sno, raw_case_id, pet, res = match

        if hall:
            current_hall = hall.strip()
            # ONLY Backfill court_hall for cases found before the hall was matched
            for orphan in orphans:
                orphan['court_hall'] = current_hall
            orphans = []
            logging.info(f"Processing Court Hall {current_hall}")
        elif cause_no:
            current_cause_list = cause_no.strip()
        elif judge_line:
            current_judges = parse_judges(judge_line)
            logging.info(f"  Judges: {current_judges}")
        elif sno:
            # 1. Search for hall footer in RES string (Pattern 1 behavior)
            res_hall_match = re.search(r"COURT\s+HALL\s+NO\s*[:]\s*(\w+)", res, re.I)
            if res_hall_match:
                current_hall = res_hall_match.group(1).strip()
                for orphan in orphans:
                    orphan['court_hall'] = current_hall
                orphans = []
            # 2. Clean RES: Remove the footer hall info if it was captured
            res = re.sub(r"COURT\s+HALL\s+NO\s*:\s*\d+", "", res, flags=re.IGNORECASE).strip()
            # Parse case details
            case_no, case_type, case_details = parse_case_details(raw_case_id)
            
            # Extract advocates TODO
            #pet_adv = extract_advocate(pet)
            #res_adv = extract_advocate(res)
            
            case_record = {
                'date': date_str,
                'court_hall': current_hall,
                'list_number': current_cause_list,
                'sl_no': sno, # Float supports 44.1
                'case_number': case_no,
                'case_type': case_type,
                'case_details': case_details if case_details != "N/A" else None,
                'judges': current_judges if current_judges != "N/A" else None,
                'petitioner_adv': pet,
                'respondent_adv': res
            }
            
            all_cases.append(case_record)
            # 4. If we haven't found a hall yet ("0"), track it to backfill it later
            if current_hall == "0":
                orphans.append(case_record)

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
