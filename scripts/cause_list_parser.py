#!/usr/bin/env python3
"""
Improved Cause List PDF Parser
Extracts all court halls, judges, case stages, and advocates from both PET and RES columns
Uses RPC for efficient database operations
"""

import os
import re
import requests
from datetime import datetime
from supabase import create_client, Client
import PyPDF2
from io import BytesIO
import logging
import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
CAUSE_LIST_URL = "https://judiciary.karnataka.gov.in/pdfs/consolidatedCauselist/blrconsolidation.pdf"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

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
        print(f"Exception:{e}")


def download_pdf(url):
    """Download PDF from URL"""
    try:
        logging.info("PDF downloaded successfully")
        return BytesIO(http_worker_call_to_supabase())
    except Exception as e:
        logging.error(f"PDF download error: {e}")
        return None


def extract_text_from_pdf(pdf_file):
    """Extract all text from PDF"""
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        full_text = ""
        
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            full_text += text + "\n"
            logging.debug(f"Extracted page {page_num + 1}")
        
        logging.info(f"Extracted {len(reader.pages)} pages from PDF")
        return full_text
    except Exception as e:
        logging.error(f"PDF text extraction error: {e}")
        return ""


def split_by_court_halls(text):
    """Split PDF text into sections by court hall"""
    hall_pattern = r'COURT HALL NO\s*:?\s*(\d+)'
    end_pattern = r'-+END-+-'
    
    halls = []
    
    # Find all court hall start positions
    hall_matches = list(re.finditer(hall_pattern, text, re.IGNORECASE))
    
    for i, match in enumerate(hall_matches):
        hall_number = match.group(1)
        start_pos = match.start()
        
        # Find the next END marker after this court hall
        end_match = re.search(end_pattern, text[start_pos:], re.IGNORECASE)
        
        if end_match:
            # End position is after the END marker
            end_pos = start_pos + end_match.end()
        else:
            # If no END marker found, use start of next hall or end of text
            end_pos = hall_matches[i + 1].start() if i + 1 < len(hall_matches) else len(text)
        
        hall_text = text[start_pos:end_pos]
        halls.append({
            'hall_number': int(hall_number),
            'text': hall_text
        })
        
        logging.info(f"Court Hall {hall_number}: {start_pos} to {end_pos}")
    
    logging.info(f"Found {len(halls)} court halls")
    return halls


def extract_judges(hall_text):
    """Extract judge names from court hall section"""
    judges = []
    
    judge_pattern = r'THE HON\'BLE JUSTICE\s+([A-Z\s\.]+?)(?=\n)'
    matches = re.findall(judge_pattern, hall_text, re.IGNORECASE)
    
    for match in matches:
        judge_name = match.strip()
        judge_name = re.sub(r'\s+', ' ', judge_name)
        judge_name = judge_name.replace('CHIEF JUSTICE', 'Chief Justice').strip()
        judge_name = judge_name.replace('JUSTICE', '').strip()
        if judge_name:
            judges.append(judge_name)
    
    primary_judge = judges[0] if len(judges) > 0 else "Unknown"
    co_judge = judges[1] if len(judges) > 1 else None
    
    return primary_judge, co_judge


def extract_cause_list_number(hall_text):
    """Extract cause list number"""
    match = re.search(r'Cause List No\.\s*(\d+)', hall_text, re.IGNORECASE)
    return int(match.group(1)) if match else 1


def extract_case_stage(lines, start_idx):
    """Extract case stage (underlined headers like ORDERS, HEARING, etc.)"""
    # Look backwards from case line to find the most recent underlined stage header
    for i in range(start_idx - 1, max(0, start_idx - 20), -1):
        line = lines[i].strip()
        # Check if next line has underline characters
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            # Underlines are typically made of repeated dashes or underscores
            if re.match(r'^[-_=]{3,}', next_line) and line:
                # Common stage patterns
                if re.search(r'(ORDERS|HEARING|ADMISSION|ARGUMENTS|FINAL|INTERLOCUTORY|APPLN|APPLICATION|MENTION)', line, re.IGNORECASE):
                    return line.strip()
        
        # Also check if the line itself looks like a stage header (all caps, short)
        if line and line.isupper() and len(line) < 60 and not line.startswith('SL.NO'):
            if re.search(r'(ORDERS|HEARING|ADMISSION|ARGUMENTS|FINAL|INTERLOCUTORY|APPLN|APPLICATION|MENTION)', line, re.IGNORECASE):
                return line.strip()
    
    return None


def parse_case_line(line):
    """Parse a case line that has columns: Sl.No | Case No | PET: info | RES: info"""
    # Pattern for case number with various types
    case_pattern = r'(\d+)\s+((?:WP|WA|CCC|MFA|COMAP|RP|PIL|CRL\.RP|MV|DM|Cr\.PC|BNSS)[^\s]*\s+\d+/\d{4})'
    
    match = re.search(case_pattern, line, re.IGNORECASE)
    if not match:
        return None
    
    sl_no = int(match.group(1))
    case_number = match.group(2).strip()
    case_type = case_number.split()[0].upper()
    
    # Split line into columns after case number
    remaining_text = line[match.end():].strip()
    
    # Find PET: and RES: positions
    pet_match = re.search(r'PET:\s*', remaining_text, re.IGNORECASE)
    res_match = re.search(r'RES:\s*', remaining_text, re.IGNORECASE)
    
    petitioner_text = ""
    respondent_text = ""
    
    if pet_match and res_match:
        # Both columns exist
        pet_start = pet_match.end()
        res_start = res_match.start()
        petitioner_text = remaining_text[pet_start:res_start].strip()
        respondent_text = remaining_text[res_match.end():].strip()
    elif pet_match:
        # Only petitioner column
        petitioner_text = remaining_text[pet_match.end():].strip()
    elif res_match:
        # Only respondent column
        respondent_text = remaining_text[res_match.end():].strip()
    
    return {
        'sl_no': sl_no,
        'case_number': case_number,
        'case_type': case_type,
        'petitioner_text': petitioner_text,
        'respondent_text': respondent_text
    }


def extract_advocate_from_text(text):
    """Extract advocate name from PET or RES column text"""
    if not text:
        return None
    
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # The advocate is typically the line that is NOT all uppercase (mixed case)
    # and comes after the party name (which is usually all uppercase)
    for line in lines:
        # Skip empty lines
        if not line:
            continue
        
        # Skip lines that are all uppercase (these are party names)
        if line.isupper():
            continue
        
        # Skip lines with specific keywords
        if re.search(r'(AND OTHERS|OTHERS|R1|R2|R3|R4|R5|NOT FILED|SD|VK)', line, re.IGNORECASE):
            continue
        
        # This is likely an advocate name (mixed case, title case)
        # Clean it up
        advocate = line.strip()
        # Remove trailing punctuation
        advocate = re.sub(r'[,;:]$', '', advocate)
        
        if advocate and len(advocate) > 2:
            return advocate
    
    return None


def extract_cases(hall_text):
    """Extract all cases with complete information from both PET and RES columns"""
    cases = []
    lines = hall_text.split('\n')
    
    current_case = None
    current_stage = None
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        # Check for case stage headers (underlined text)
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if re.match(r'^[-_=]{3,}', next_line):
                if re.search(r'(ORDERS|HEARING|ADMISSION|ARGUMENTS|FINAL|INTERLOCUTORY|APPLN|APPLICATION|MENTION)', line_stripped, re.IGNORECASE):
                    current_stage = line_stripped
                    logging.debug(f"Found case stage: {current_stage}")
                    continue
        
        # Try to parse this line as a case
        parsed = parse_case_line(line)
        
        if parsed:
            # Create case record
            case_record = {
                'sl_no': parsed['sl_no'],
                'case_number': parsed['case_number'],
                'case_type': parsed['case_type'],
                'case_stage': current_stage,
                'petitioner_text': parsed['petitioner_text'],
                'respondent_text': parsed['respondent_text'],
                'petitioner_advocate': None,
                'respondent_advocate': None,
                'petitioner_name': None,
                'respondent_name': None
            }
            
            # Look ahead for continuation lines (party names and advocates)
            continuation_text_pet = parsed['petitioner_text']
            continuation_text_res = parsed['respondent_text']
            
            # Collect next few lines for this case
            for j in range(i + 1, min(i + 10, len(lines))):
                next_line = lines[j].strip()
                
                # Stop if we hit another case number
                if re.match(r'^\d+\s+(?:WP|WA|CCC|MFA|COMAP|RP|PIL|CRL|MV)', next_line, re.IGNORECASE):
                    break
                
                # Stop if we hit a stage header
                if j + 1 < len(lines) and re.match(r'^[-_=]{3,}', lines[j + 1].strip()):
                    break
                
                if not next_line:
                    continue
                
                # Determine if this line belongs to PET or RES column based on position
                # This is approximate - in reality, we'd need to parse column positions
                # For now, we'll add to both and extract advocates from the combined text
                if 'RES:' not in next_line and 'PET:' not in next_line:
                    continuation_text_pet += '\n' + next_line
                    continuation_text_res += '\n' + next_line
            
            # Extract petitioner name (first all-caps line)
            pet_lines = [l.strip() for l in continuation_text_pet.split('\n') if l.strip()]
            for pet_line in pet_lines:
                if pet_line.isupper() and len(pet_line) > 3:
                    case_record['petitioner_name'] = pet_line
                    break
            
            # Extract respondent name (first all-caps line)
            res_lines = [l.strip() for l in continuation_text_res.split('\n') if l.strip()]
            for res_line in res_lines:
                if res_line.isupper() and len(res_line) > 3:
                    case_record['respondent_name'] = res_line
                    break
            
            # Extract advocates
            case_record['petitioner_advocate'] = extract_advocate_from_text(continuation_text_pet)
            case_record['respondent_advocate'] = extract_advocate_from_text(continuation_text_res)
            
            cases.append(case_record)
            
            logging.debug(f"Case {case_record['case_number']}: Stage={current_stage}, Pet Adv={case_record['petitioner_advocate']}, Res Adv={case_record['respondent_advocate']}")
    
    logging.info(f"Extracted {len(cases)} cases from section")
    return cases


def parse_cause_list_pdf(pdf_file):
    """Main parsing function - extracts all data from PDF"""
    all_cases = []
    
    full_text = extract_text_from_pdf(pdf_file)
    if not full_text:
        return []
    
    court_halls = split_by_court_halls(full_text)
    
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    for hall_data in court_halls:
        hall_number = hall_data['hall_number']
        hall_text = hall_data['text']
        
        logging.info(f"Processing Court Hall {hall_number}")
        
        primary_judge, co_judge = extract_judges(hall_text)
        logging.info(f"  Judge: {primary_judge}" + (f", {co_judge}" if co_judge else ""))
        
        list_number = extract_cause_list_number(hall_text)
        
        cases = extract_cases(hall_text)
        logging.info(f"  Found {len(cases)} cases")
        
        for case in cases:
            # Collect all advocates
            all_advocates = []
            if case['petitioner_advocate']:
                all_advocates.append(case['petitioner_advocate'])
            if case['respondent_advocate']:
                all_advocates.append(case['respondent_advocate'])
            
            case_record = {
                'date': date_str,
                'court_hall': hall_number,
                'list_number': list_number,
                'sl_no': case['sl_no'],
                'case_number': case['case_number'],
                'case_type': case['case_type'],
                'case_stage': case['case_stage'],
                'judge_name': primary_judge,
                'co_judge_name': co_judge,
                'petitioner_name': case['petitioner_name'],
                'petitioner_advocate': case['petitioner_advocate'],
                'respondent_name': case['respondent_name'],
                'respondent_advocate': case['respondent_advocate'],
                'all_advocates': all_advocates
            }
            
            all_cases.append(case_record)
    
    logging.info(f"Total cases parsed: {len(all_cases)}")
    return all_cases


def insert_to_supabase(cases):
    """Insert parsed cases into Supabase using RPC for better performance"""
    if not cases:
        logging.warning("No cases to insert")
        return
    
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Call the stored procedure with all cases at once
        logging.info(f"Calling RPC function with {len(cases)} cases...")
        result = supabase.rpc('insert_cause_list_cases', {'cases_data': cases}).execute()
        
        # Extract statistics from result
        if result.data and len(result.data) > 0:
            stats = result.data[0]
            inserted = stats.get('inserted_count', 0)
            updated = stats.get('updated_count', 0)
            duplicates = stats.get('duplicate_count', 0)
            
            logging.info(f"Database operation completed:")
            logging.info(f"  - Inserted: {inserted} new cases")
            logging.info(f"  - Updated: {updated} existing cases")
            logging.info(f"  - Duplicates removed: {duplicates}")
            logging.info(f"  - Total processed: {inserted + updated}")
        else:
            logging.info(f"Processed {len(cases)} cases")
        
        # Log summary by court hall
        from collections import defaultdict
        hall_counts = defaultdict(int)
        stage_counts = defaultdict(int)
        
        for case in cases:
            hall_counts[case['court_hall']] += 1
            if case['case_stage']:
                stage_counts[case['case_stage']] += 1
        
        logging.info("Cases by court hall:")
        for hall, count in sorted(hall_counts.items()):
            logging.info(f"  Court Hall {hall}: {count} cases")
        
        logging.info("Cases by stage:")
        for stage, count in sorted(stage_counts.items()):
            logging.info(f"  {stage}: {count} cases")
        
    except Exception as e:
        logging.error(f"Supabase RPC error: {e}")
        logging.error(f"Error details: {str(e)}")


def main():
    """Main execution"""
    logging.info("="*60)
    logging.info("Starting Cause List Parser")
    logging.info("="*60)
    
    pdf_file = download_pdf(CAUSE_LIST_URL)
    if not pdf_file:
        logging.error("Failed to download PDF")
        return
    
    cases = parse_cause_list_pdf(pdf_file)
   
    if cases:
        logging.info(f"Successfully parsed {len(cases)} total cases")
        insert_to_supabase(cases)
        logging.info("Cause list parsing completed successfully")
    else:
        logging.error("No cases were parsed from PDF")


if __name__ == "__main__":
    main()
