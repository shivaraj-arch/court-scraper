#!/usr/bin/env python3
"""
End of Day (EOD) Processor
Compares scheduled vs heard cases and generates statistics
"""

import os
from datetime import datetime, timedelta
from supabase import create_client, Client
import logging

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def process_eod():
    """Process end of day statistics"""
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        logging.info(f"Processing EOD for {date_str}")
        
        # Update case_status_tracker with heard cases
        heard_cases = supabase.table('heard_cases').select('*').eq('date', date_str).execute()
        
        for case in heard_cases.data:
            supabase.table('case_status_tracker').update({
                'was_heard': True,
                'outcome': 'heard'
            }).eq('date', date_str).eq('case_number', case['case_number']).execute()
        
        # Mark unheard cases as 'not_reached'
        supabase.table('case_status_tracker').update({
            'outcome': 'not_reached'
        }).eq('date', date_str).eq('was_scheduled', True).eq('was_heard', False).execute()
        
        # Generate judge statistics
        generate_judge_stats(supabase, date_str)
        
        # Generate advocate statistics
        generate_advocate_stats(supabase, date_str)
        
        # Update case history
        update_case_history(supabase, date_str)
        
        logging.info("EOD processing completed")
        
    except Exception as e:
        logging.error(f"EOD processing error: {e}")

def generate_judge_stats(supabase, date_str):
    """Generate judge statistics for the day"""
    # Get all court halls for the day
    scheduled = supabase.table('cause_list_cases').select('court_hall, judge_name').eq('date', date_str).execute()
    
    for record in scheduled.data:
        court_hall = record['court_hall']
        judge_name = record['judge_name']
        
        # Count scheduled
        scheduled_count = supabase.table('cause_list_cases').select(
            'id', count='exact'
        ).eq('date', date_str).eq('court_hall', court_hall).execute().count
        
        # Count heard
        heard_count = supabase.table('heard_cases').select(
            'id', count='exact'
        ).eq('date', date_str).eq('court_hall', court_hall).execute().count
        
        # Calculate efficiency
        hearing_efficiency = (heard_count / scheduled_count * 100) if scheduled_count > 0 else 0
        
        # Insert stats
        supabase.table('judge_statistics').upsert({
            'date': date_str,
            'court_hall': court_hall,
            'judge_name': judge_name,
            'cases_scheduled': scheduled_count,
            'cases_heard': heard_count,
            'cases_not_reached': scheduled_count - heard_count,
            'hearing_efficiency': round(hearing_efficiency, 2)
        }, on_conflict='date,court_hall,judge_name').execute()
    
    logging.info("Judge statistics generated")

def generate_advocate_stats(supabase, date_str):
    """Generate advocate statistics for the day"""
    # This would require parsing advocate names from cause_list_cases
    # Simplified version here
    logging.info("Advocate statistics generation skipped (requires advocate parsing)")

def update_case_history(supabase, date_str):
    """Update long-term case history"""
    # Get all cases from today
    cases = supabase.table('case_status_tracker').select('*').eq('date', date_str).execute()
    
    for case in cases.data:
        case_number = case['case_number']
        
        # Check if case exists in history
        existing = supabase.table('case_history').select('*').eq('case_number', case_number).execute()
        
        if existing.data:
            # Update existing
            hist = existing.data[0]
            supabase.table('case_history').update({
                'last_listed_date': date_str,
                'total_listings': hist['total_listings'] + 1,
                'total_hearings': hist['total_hearings'] + (1 if case['was_heard'] else 0),
                'updated_at': datetime.now().isoformat()
            }).eq('case_number', case_number).execute()
        else:
            # Insert new
            supabase.table('case_history').insert({
                'case_number': case_number,
                'first_listed_date': date_str,
                'last_listed_date': date_str,
                'total_listings': 1,
                'total_hearings': 1 if case['was_heard'] else 0,
                'current_status': 'pending'
            }).execute()
    
    logging.info("Case history updated")

if __name__ == "__main__":
    process_eod()
