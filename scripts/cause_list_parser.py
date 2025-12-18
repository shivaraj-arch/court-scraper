#!/usr/bin/env python3
"""
Cause List PDF Parser for GitHub Actions
Downloads daily cause list PDF and parses it into Supabase
"""

import os
import re
import requests
from datetime import datetime
from supabase import create_client, Client
import PyPDF2
from io import BytesIO
import logging

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
CAUSE_LIST_URL = "https://judiciary.karnataka.gov.in/pdfs/consolidatedCauselist/blrconsolidation.pdf"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def http_worker_call_to_supabase():
    url: str = "https://gthnjueqoufdtwtzjcxg.supabase.co/functions/v1/http-worker"
    supabase: Client = create_client(url, SUPABASE_KEY)
    try:
        # Invoke the function
        response = supabase.functions.invoke(
            "http-worker", # Name of your Edge Function
            invoke_options={
                "body": {"targetUrl": CAUSE_LIST_URL},
                "method": "POST"
            }
        )
        # Access the downloaded data
        # If the function returns a file, 'response.content' will contain the binary data
        return response
        """
        with open("downloaded_file.pdf", "wb") as f:
            f.write(response)
        print("Download complete.")
        """
    except Exception as e:
        print(f"Exception:{e}")

def download_pdf(url):
    """Download PDF from URL"""
    try:
        #response = requests.get(url, timeout=30)
        #response.raise_for_status()
        #return BytesIO(response.content)
        return BytesIO(http_worker_call_to_supabase())
    except Exception as e:
        logging.error(f"PDF download error: {e}")
        return None

def parse_cause_list_pdf(pdf_file):
    """Parse cause list PDF and extract case data"""
    cases = []
    
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        full_text = ""
        
        for page in reader.pages:
            full_text += page.extract_text()
        
        # Extract court hall and judges
        court_hall_match = re.search(r'COURT HALL NO\s*:?\s*(\d+)', full_text, re.IGNORECASE)
        court_hall = int(court_hall_match.group(1)) if court_hall_match else 1
        
        # Extract judges
        judge_pattern = r'THE HON\'BLE\s+(.+?)(?=\n|&)'
        judges = re.findall(judge_pattern, full_text)
        judge_name = judges[0].strip() if judges else "Unknown"
        co_judge = judges[1].strip() if len(judges) > 1 else None
        
        # Extract cause list number
        list_match = re.search(r'Cause List No\.\s*(\d+)', full_text)
        list_number = int(list_match.group(1)) if list_match else 1
        
        # Extract cases - pattern for case numbers
        case_pattern = r'(\d+)\s+((?:WP|WA|CCC|MFA|COMAP|RP)\s+\d+/\d{4})'
        case_matches = re.findall(case_pattern, full_text)
        
        # Extract advocate names - simplified pattern
        advocate_pattern = r'\n([A-Z\s\.]{3,}(?:ADVOCATE|FOR)?\s*(?:FOR\s+[A-Z0-9]+)?)'
        
        for sl_no, case_number in case_matches:
            # Find case type
            case_type = case_number.split()[0]
            
            cases.append({
                'date': datetime.now().strftime('%Y-%m-%d'),
                'court_hall': court_hall,
                'list_number': list_number,
                'sl_no': int(sl_no),
                'case_number': case_number,
                'case_type': case_type,
                'judge_name': judge_name,
                'co_judge_name': co_judge,
            })
        
        logging.info(f"Parsed {len(cases)} cases from PDF")
        return cases
    
    except Exception as e:
        logging.error(f"PDF parsing error: {e}")
        return []

def insert_to_supabase(cases):
    """Insert parsed cases into Supabase"""
    if not cases:
        logging.info("No cases to insert")
        return
    
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Use upsert to avoid duplicates
        result = supabase.table('cause_list_cases').upsert(
            cases,
            on_conflict='date,court_hall,case_number'
        ).execute()
        
        logging.info(f"Inserted {len(cases)} cases into cause_list_cases")
        
        # Also create entries in case_status_tracker
        tracker_records = [
            {
                'date': case['date'],
                'court_hall': case['court_hall'],
                'case_number': case['case_number'],
                'was_scheduled': True,
                'was_heard': False
            }
            for case in cases
        ]
        
        supabase.table('case_status_tracker').upsert(
            tracker_records,
            on_conflict='date,court_hall,case_number'
        ).execute()
        
        logging.info(f"Updated case_status_tracker")
        
    except Exception as e:
        logging.error(f"Supabase insert error: {e}")

def main():
    """Main execution"""
    logging.info("Starting cause list parser")
    
    pdf_file = download_pdf(CAUSE_LIST_URL)
    if not pdf_file:
        logging.error("Failed to download PDF")
        return
    
    cases = parse_cause_list_pdf(pdf_file)
    
    if cases:
        insert_to_supabase(cases)




if __name__ == "__main__":
    main()
