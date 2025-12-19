#!/usr/bin/env python3
"""
Display Board Scraper for GitHub Actions
Scrapes court display board and stores in Supabase
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime, time
from supabase import create_client, Client
import logging

# Configuration from environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
DISPLAY_BOARD_URL = "https://judiciary.karnataka.gov.in/display_board_bench.php"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')


def http_worker_call_to_supabase():
    url: str = "https://gthnjueqoufdtwtzjcxg.supabase.co/functions/v1/http-responder"
    supabase: Client = create_client(url, SUPABASE_KEY)
    try:
        # Invoke the function
        response = supabase.functions.invoke(
            "http-responder", # Name of your Edge Function
            invoke_options={
                "body": {"targetUrl": DISPLAY_BOARD_URL},
                "method": "POST"
            }
        )
        # Access the downloaded data
        # If the function returns a file, 'response.content' will contain the binary data
        return response
    except Exception as e:
        print(f"Exception:{e}")


def scrape_display_board():
    """Scrape the display board"""
    try:
        """
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(DISPLAY_BOARD_URL, headers=headers, timeout=10)
        response.raise_for_status()
        """
        response = http_worker_call_to_supabase()
        #soup = BeautifulSoup(response.content, 'html.parser')
        soup = BeautifulSoup(response, 'html.parser')
        records = []
        
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')[1:]
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    ch_no = cols[0].get_text(strip=True)
                    list_no = cols[1].get_text(strip=True)
                    case_no = cols[3].get_text(strip=True)
                    
                    if ch_no and list_no and case_no:
                        records.append({
                            'ch_no': int(ch_no) if ch_no.isdigit() else ch_no,
                            'list_no': int(list_no) if list_no.isdigit() else list_no,
                            'case_no': case_no
                        })
        
        return records
    except Exception as e:
        logging.error(f"Scraping error: {e}")
        return []

def update_supabase_recordwise(records):
    """Update Supabase with heard cases"""
    if not records:
        logging.info("No records to update")
        return 0
    
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        date_str = datetime.now().strftime('%Y-%m-%d')
        timestamp = datetime.now().isoformat()
        new_count = 0
        
        for record in records:
            ch_no = record['ch_no']
            list_no = record['list_no']
            case_no = record['case_no']
            
            # Check if case already exists
            existing = supabase.table('heard_cases').select('id', 'total_appearances').eq(
                'date', date_str
            ).eq('court_hall', ch_no).eq('case_number', case_no).execute()
            
            if existing.data:
                # Update: increment appearances, update last_heard_at
                case_id = existing.data[0]['id']
                appearances = existing.data[0]['total_appearances'] + 1
                
                supabase.table('heard_cases').update({
                    'last_heard_at': timestamp,
                    'total_appearances': appearances,
                    'updated_at': timestamp
                }).eq('id', case_id).execute()
            else:
                # Insert new case
                supabase.table('heard_cases').insert({
                    'date': date_str,
                    'court_hall': ch_no,
                    'list_number': list_no,
                    'case_number': case_no,
                    'first_heard_at': timestamp,
                    'last_heard_at': timestamp,
                    'total_appearances': 1,
                    'status': 'in_progress'
                }).execute()
                new_count += 1
        
        logging.info(f"Updated Supabase: {new_count} new cases, {len(records)-new_count} updated")
        return new_count
    
    except Exception as e:
        logging.error(f"Supabase error: {e}")
        return 0


def upsert_supabase_batch(records):
    """
    Sends all records in ONE request.
    The DB handles duplication logic and appearance increments.
    """
    if not records:
        return 0

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        now_iso = datetime.now().isoformat()
        today_str = datetime.now().strftime('%Y-%m-%d')

        payload = [{
            'date': today_str,
            'court_hall': r['ch_no'],    # Function casts this to int
            'list_number': r['list_no'], # Function casts this to int
            'case_number': r['case_no'], # Function casts this to text
            'timestamp': now_iso         # Function casts this to timestamptz
        } for r in records]

        # Single API Call
        supabase.rpc('batch_upsert_cases', {'payload': payload}).execute()

        return len(records)
    except Exception as e:
        logging.error(f"Supabase RPC error: {e}")
        return 0



def main():
    """Main execution"""
    logging.info("Starting display board scraper")
   
    """ not needed as checked in yml
    # Check working hours (IST)
    now = datetime.now()
    if not (time(10, 25) <= now.time() <= time(17, 30)):
        logging.info("Outside court hours, skipping")
        return
    """
    records = scrape_display_board()
    logging.info(f"Scraped {len(records)} records")
    
    try:
        if records:
            upsert_supabase_batch(records)
    except Exception as e:
        logging.error(f"Supabase Outer Upsert error: {e}")
        return 0

if __name__ == "__main__":
    main()
