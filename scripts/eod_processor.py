#!/usr/bin/env python3
"""
End of Day (EOD) Processor
Compares cause_list (scheduled) vs heard_cases (actual) and generates statistics
"""

import os
from datetime import datetime
from supabase import create_client, Client
import logging

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',    handlers=[
        logging.FileHandler('app.log'),  # Creates log file
        logging.StreamHandler()  # Also logs to console
        ])


def process_eod(target_date=None):
    """Process end of day statistics"""
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        date_str = target_date or datetime.now().strftime('%Y-%m-%d')
        
        logging.info(f"="*60)
        logging.info(f"Processing EOD for {date_str}")
        logging.info(f"="*60)
        
        # Get all scheduled cases for the day from cause_list
        scheduled_cases = supabase.table('cause_list').select('*').eq('date', date_str).execute()
        
        if not scheduled_cases.data:
            logging.warning(f"No scheduled cases found for {date_str}")
            return
        
        logging.info(f"Found {len(scheduled_cases.data)} scheduled cases")
        
        # Get all heard cases for the day
        heard_cases = supabase.table('heard_cases').select('*').eq('date', date_str).execute()
        logging.info(f"Found {len(heard_cases.data)} heard cases")
        
        # Create lookup set of heard case numbers
        heard_case_numbers = {case['case_number'] for case in heard_cases.data}
        
        # Count statistics
        heard_count = len(heard_case_numbers)
        scheduled_count = len(scheduled_cases.data)
        not_reached_count = scheduled_count - heard_count
        overall_efficiency = (heard_count / scheduled_count * 100) if scheduled_count > 0 else 0
        
        logging.info(f"Cases heard: {heard_count}")
        logging.info(f"Cases not reached: {not_reached_count}")
        logging.info(f"Overall efficiency: {overall_efficiency:.1f}%")
        
        # Generate statistics by court hall
        generate_hall_stats(supabase, date_str, scheduled_cases.data, heard_case_numbers)
        
        # Generate and save judge statistics
        generate_judge_stats(supabase, date_str, scheduled_cases.data, heard_case_numbers)
        
        # Save daily summary
        save_daily_summary(supabase, date_str, scheduled_count, heard_count, not_reached_count, overall_efficiency, scheduled_cases.data)
        
        # Update case history
        update_case_history(supabase, date_str, scheduled_cases.data, heard_case_numbers)
        
        logging.info(f"="*60)
        logging.info("EOD processing completed successfully")
        logging.info(f"="*60)
        
    except Exception as e:
        logging.error(f"EOD processing error: {e}")
        raise


def generate_hall_stats(supabase, date_str, scheduled_cases, heard_case_numbers):
    """Generate statistics by court hall"""
    from collections import defaultdict
    
    hall_stats = defaultdict(lambda: {'scheduled': 0, 'heard': 0})
    
    for case in scheduled_cases:
        hall = case['court_hall']
        hall_stats[hall]['scheduled'] += 1
        
        if case['case_number'] in heard_case_numbers:
            hall_stats[hall]['heard'] += 1
    
    logging.info("\nStatistics by Court Hall:")
    for hall in sorted(hall_stats.keys()):
        stats = hall_stats[hall]
        scheduled = stats['scheduled']
        heard = stats['heard']
        efficiency = (heard / scheduled * 100) if scheduled > 0 else 0
        
        logging.info(f"  Court Hall {hall}:")
        logging.info(f"    Scheduled: {scheduled}")
        logging.info(f"    Heard: {heard}")
        logging.info(f"    Not reached: {scheduled - heard}")
        logging.info(f"    Efficiency: {efficiency:.1f}%")


def generate_judge_stats(supabase, date_str, scheduled_cases, heard_case_numbers):
    """Generate judge statistics for the day and save to database"""
    from collections import defaultdict
    
    # Group by judge
    judge_stats = defaultdict(lambda: {
        'court_hall': None,
        'scheduled': 0,
        'heard': 0
    })
    
    for case in scheduled_cases:
        judge = case.get('judges', 'Unknown')
        court_hall = case['court_hall']
        
        judge_stats[judge]['court_hall'] = court_hall
        judge_stats[judge]['scheduled'] += 1
        
        if case['case_number'] in heard_case_numbers:
            judge_stats[judge]['heard'] += 1
    
    # Prepare records for database
    judge_records = []
    
    logging.info("\nStatistics by Judge:")
    for judge, stats in judge_stats.items():
        scheduled = stats['scheduled']
        heard = stats['heard']
        efficiency = (heard / scheduled * 100) if scheduled > 0 else 0
        
        logging.info(f"  {judge}:")
        logging.info(f"    Court Hall: {stats['court_hall']}")
        logging.info(f"    Scheduled: {scheduled}")
        logging.info(f"    Heard: {heard}")
        logging.info(f"    Efficiency: {efficiency:.1f}%")
        
        judge_records.append({
            'date': date_str,
            'court_hall': stats['court_hall'],
            'judge_name': judge,
            'cases_scheduled': scheduled,
            'cases_heard': heard,
            'cases_not_reached': scheduled - heard,
            'hearing_efficiency': round(efficiency, 2)
        })
    
    # Save to database
    try:
        supabase.table('judge_statistics').upsert(
            judge_records,
            on_conflict='date,court_hall,judge_name'
        ).execute()
        logging.info("Judge statistics saved to database")
    except Exception as e:
        logging.error(f"Could not save judge statistics: {e}")


def save_daily_summary(supabase, date_str, scheduled, heard, not_reached, efficiency, scheduled_cases):
    """Save daily summary statistics"""
    # Count unique court halls
    court_halls = set(case['court_hall'] for case in scheduled_cases)
    
    summary = {
        'date': date_str,
        'total_scheduled': scheduled,
        'total_heard': heard,
        'total_not_reached': not_reached,
        'overall_efficiency': round(efficiency, 2),
        'total_court_halls': len(court_halls)
    }
    
    try:
        supabase.table('daily_summary').upsert(summary).execute()
        logging.info("Daily summary saved to database")
    except Exception as e:
        logging.error(f"Could not save daily summary: {e}")


def update_case_history(supabase, date_str, scheduled_cases, heard_case_numbers):
    """Update long-term case history"""
    
    logging.info("\nUpdating case history...")
    
    for case in scheduled_cases:
        case_number = case['case_number']
        was_heard = case_number in heard_case_numbers
        
        # Check if case exists in history
        try:
            existing = supabase.table('case_history').select('*').eq('case_number', case_number).execute()
            
            if existing.data and len(existing.data) > 0:
                # Update existing
                hist = existing.data[0]
                supabase.table('case_history').update({
                    'last_listed_date': date_str,
                    'total_listings': hist.get('total_listings', 0) + 1,
                    'total_hearings': hist.get('total_hearings', 0) + (1 if was_heard else 0),
                    'current_status': 'heard' if was_heard else 'pending',
                    'updated_at': datetime.now().isoformat()
                }).eq('case_number', case_number).execute()
            else:
                # Insert new
                supabase.table('case_history').insert({
                    'case_number': case_number,
                    'case_type': case.get('case_type'),
                    'first_listed_date': date_str,
                    'last_listed_date': date_str,
                    'total_listings': 1,
                    'total_hearings': 1 if was_heard else 0,
                    'current_status': 'heard' if was_heard else 'pending'
                }).execute()
        except Exception as e:
            # Table might not exist yet
            logging.debug(f"Could not update case history for {case_number}: {e}")
            continue
    
    logging.info("Case history updated")


def generate_summary_report(supabase, date_str):
    """Generate a summary report for the day"""
    try:
        scheduled = supabase.table('cause_list').select('case_number', count='exact').eq('date', date_str).execute()
        heard = supabase.table('heard_cases').select('case_number', count='exact').eq('date', date_str).execute()
        
        scheduled_count = scheduled.count if scheduled.count else 0
        heard_count = heard.count if heard.count else 0
        
        efficiency = (heard_count / scheduled_count * 100) if scheduled_count > 0 else 0
        
        print(f"\n{'='*60}")
        print(f"DAILY SUMMARY REPORT - {date_str}")
        print(f"{'='*60}")
        print(f"Total Cases Scheduled: {scheduled_count}")
        print(f"Total Cases Heard: {heard_count}")
        print(f"Total Cases Not Reached: {scheduled_count - heard_count}")
        print(f"Overall Efficiency: {efficiency:.1f}%")
        print(f"{'='*60}\n")
        
    except Exception as e:
        logging.warning(f"Could not generate summary report: {e}")


if __name__ == "__main__":
    import sys
    
    # Allow passing date as argument: python eod_processor.py 2025-01-15
    target_date = sys.argv[1] if len(sys.argv) > 1 else None
    
    process_eod(target_date)
    
    # Generate summary report
    date_str = target_date or datetime.now().strftime('%Y-%m-%d')
    generate_summary_report(create_client(SUPABASE_URL, SUPABASE_KEY), date_str)
