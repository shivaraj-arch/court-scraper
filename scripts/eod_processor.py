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
        
        # Optimization: Move all logic to a single RPC call to handle bulk updates and aggregations
        # This fixes the N+1 query problem and reduces egress costs
        result = supabase.rpc('process_eod_logic', {'p_date': date_str}).execute()
        
        if not result.data or not result.data.get('summary'):
            logging.warning(f"No scheduled cases found for {date_str} or processing returned no data")
            return
            
        data = result.data
        summary = data['summary']
        
        logging.info(f"Found {summary['total_scheduled']} scheduled cases")
        logging.info(f"Found {summary['total_heard']} heard cases")
        
        logging.info(f"Cases heard: {summary['total_heard']}")
        logging.info(f"Cases not reached: {summary['total_not_reached']}")
        logging.info(f"Overall efficiency: {summary['overall_efficiency']}%")
        
        # Generate statistics by court hall from returned data
        generate_hall_stats(data.get('hall_stats', []))
        
        # Generate and save judge statistics from returned data
        generate_judge_stats(data.get('judge_stats', []))
        
        # Daily summary is already saved by the RPC
        logging.info("Daily summary saved to database via RPC")
        
        # Case history is already updated by the RPC
        logging.info("Case history updated via RPC bulk upsert")
        
        logging.info(f"="*60)
        logging.info("EOD processing completed successfully")
        logging.info(f"="*60)
        
    except Exception as e:
        logging.error(f"EOD processing error: {e}")
        raise


def generate_hall_stats(hall_data):
    """Generate statistics by court hall from pre-calculated data"""
    if not hall_data:
        return

    logging.info("\nStatistics by Court Hall:")
    for stats in sorted(hall_data, key=lambda x: x['court_hall']):
        hall = stats['court_hall']
        scheduled = stats['scheduled']
        heard = stats['heard']
        efficiency = (heard / scheduled * 100) if scheduled > 0 else 0
        
        logging.info(f"  Court Hall {hall}:")
        logging.info(f"    Scheduled: {scheduled}")
        logging.info(f"    Heard: {heard}")
        logging.info(f"    Not reached: {scheduled - heard}")
        logging.info(f"    Efficiency: {efficiency:.1f}%")


def generate_judge_stats(judge_data):
    """Log judge statistics from pre-calculated data"""
    if not judge_data:
        return

    logging.info("\nStatistics by Judge:")
    for stats in judge_data:
        judge = stats['judge_name']
        scheduled = stats['cases_scheduled']
        heard = stats['cases_heard']
        efficiency = stats['hearing_efficiency']
        
        logging.info(f"  {judge}:")
        logging.info(f"    Court Hall: {stats['court_hall']}")
        logging.info(f"    Scheduled: {scheduled}")
        logging.info(f"    Heard: {heard}")
        logging.info(f"    Efficiency: {efficiency}%")


def save_daily_summary(supabase, date_str, scheduled, heard, not_reached, efficiency, scheduled_cases):
    """Deprecated: Logic moved to process_eod_logic RPC"""
    pass


def update_case_history(supabase, date_str, scheduled_cases, heard_case_numbers):
    """Deprecated: Logic moved to process_eod_logic RPC"""
    pass


def generate_summary_report(supabase, date_str):
    """Generate a summary report for the day"""
    try:
        # Optimization: Fetch from daily_summary table instead of re-counting tables
        res = supabase.table('daily_summary').select('*').eq('date', date_str).execute()
        
        if res.data:
            summary = res.data[0]
            print(f"\n{'='*60}")
            print(f"DAILY SUMMARY REPORT - {date_str}")
            print(f"{'='*60}")
            print(f"Total Cases Scheduled: {summary['total_scheduled']}")
            print(f"Total Cases Heard: {summary['total_heard']}")
            print(f"Total Cases Not Reached: {summary['total_not_reached']}")
            print(f"Overall Efficiency: {summary['overall_efficiency']}%")
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
