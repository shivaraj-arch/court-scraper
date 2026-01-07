#!/usr/bin/env python3
"""
Dashboard Generator for Karnataka High Court Statistics
Generates static HTML dashboard from EOD data
"""

import os
from datetime import datetime, timedelta
from supabase import create_client, Client
import logging

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TRACKING_START_DATE = "2026-01-02"  # When we started tracking

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',    handlers=[
        logging.FileHandler('app.log'),  # Creates log file
        logging.StreamHandler()  # Also logs to console
        ])


def generate_dashboard():
    """Generate HTML dashboard with court statistics"""
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        logging.info("Generating dashboard...")
        
        # Get latest date
        latest = supabase.table('daily_summary').select('date').order('date', desc=True).limit(1).execute()
        if not latest.data:
            logging.warning("No data available for dashboard")
            return
        
        latest_date = latest.data[0]['date']
        
        # Fetch data
        daily_summary = get_daily_summary(supabase, latest_date)
        judge_stats = get_judge_statistics(supabase, latest_date)
        weekly_trend = get_weekly_trend(supabase)
        monthly_stats = get_monthly_stats(supabase)
        top_judges = get_top_judges_monthly(supabase)
        
        # Generate HTML
        html = generate_html(
            latest_date,
            daily_summary,
            judge_stats,
            weekly_trend,
            monthly_stats,
            top_judges
        )
        
        # Write to file
        output_path = "docs/index.html"
        os.makedirs("docs", exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logging.info(f"Dashboard generated: {output_path}")
        
    except Exception as e:
        logging.error(f"Dashboard generation error: {e}")
        raise


def get_daily_summary(supabase, date):
    """Get daily summary for specific date"""
    result = supabase.table('daily_summary').select('*').eq('date', date).execute()
    return result.data[0] if result.data else None


def get_judge_statistics(supabase, date):
    """Get judge statistics for specific date"""
    result = supabase.table('judge_statistics').select('*').eq('date', date).order('hearing_efficiency', desc=True).execute()
    return result.data


def get_weekly_trend(supabase):
    """Get last 7 days trend"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=6)
    
    result = supabase.table('daily_summary').select('*').gte('date', str(start_date)).lte('date', str(end_date)).order('date').execute()
    return result.data


def get_monthly_stats(supabase):
    """Get current month statistics"""
    today = datetime.now()
    month_start = today.replace(day=1).strftime('%Y-%m-%d')
    
    result = supabase.table('daily_summary').select('*').gte('date', month_start).execute()
    
    if not result.data:
        return None
    
    total_scheduled = sum(d['total_scheduled'] for d in result.data)
    total_heard = sum(d['total_heard'] for d in result.data)
    
    return {
        'month': today.strftime('%B %Y'),
        'days': len(result.data),
        'total_scheduled': total_scheduled,
        'total_heard': total_heard,
        'efficiency': round((total_heard / total_scheduled * 100) if total_scheduled > 0 else 0, 2)
    }


def get_top_judges_monthly(supabase):
    """Get top performing judges for current month"""
    today = datetime.now()
    month_start = today.replace(day=1).strftime('%Y-%m-%d')
    
    # Use SQL query for aggregation
    result = supabase.rpc('get_top_judges_month', {'start_date': month_start}).execute()
    
    # Fallback if RPC doesn't exist
    if not result.data:
        judges = supabase.table('judge_statistics').select('*').gte('date', month_start).execute()
        
        from collections import defaultdict
        judge_agg = defaultdict(lambda: {'scheduled': 0, 'heard': 0})
        
        for stat in judges.data:
            judge = stat['judge_name']
            judge_agg[judge]['scheduled'] += stat['cases_scheduled']
            judge_agg[judge]['heard'] += stat['cases_heard']
        
        top = []
        for judge, data in judge_agg.items():
            efficiency = (data['heard'] / data['scheduled'] * 100) if data['scheduled'] > 0 else 0
            top.append({
                'judge_name': judge,
                'total_heard': data['heard'],
                'total_scheduled': data['scheduled'],
                'efficiency': round(efficiency, 2)
            })
        
        return sorted(top, key=lambda x: x['efficiency'], reverse=True)[:10]
    
    return result.data[:10]


def generate_html(latest_date, daily, judges, weekly, monthly, top_judges):
    """Generate complete HTML dashboard"""
    
    # Calculate some stats
    daily_efficiency = daily['overall_efficiency'] if daily else 0
    daily_scheduled = daily['total_scheduled'] if daily else 0
    daily_heard = daily['total_heard'] if daily else 0
    
    # Generate weekly chart data
    weekly_dates = [d['date'] for d in weekly] if weekly else []
    weekly_efficiency = [d['overall_efficiency'] for d in weekly] if weekly else []
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Karnataka High Court - Daily Statistics</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}
        
        .header h1 {{
            color: #2d3748;
            font-size: 2.5rem;
            margin-bottom: 10px;
        }}
        
        .header .subtitle {{
            color: #718096;
            font-size: 1.1rem;
        }}
        
        .disclaimer {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
        }}
        
        .disclaimer strong {{
            color: #856404;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
        }}
        
        .stat-card .label {{
            color: #718096;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}
        
        .stat-card .value {{
            color: #2d3748;
            font-size: 2.5rem;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .stat-card .change {{
            font-size: 0.9rem;
            color: #48bb78;
        }}
        
        .chart-container {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        
        .chart-container h2 {{
            color: #2d3748;
            margin-bottom: 20px;
        }}
        
        .judge-table {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            overflow-x: auto;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        th {{
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        
        td {{
            padding: 15px;
            border-bottom: 1px solid #e2e8f0;
        }}
        
        tr:hover {{
            background: #f7fafc;
        }}
        
        .efficiency-bar {{
            height: 8px;
            background: #e2e8f0;
            border-radius: 4px;
            overflow: hidden;
        }}
        
        .efficiency-fill {{
            height: 100%;
            background: linear-gradient(90deg, #48bb78, #38a169);
            transition: width 0.3s ease;
        }}
        
        .footer {{
            text-align: center;
            color: white;
            margin-top: 30px;
            padding: 20px;
        }}
        
        .badge {{
            display: inline-block;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }}
        
        .badge-success {{
            background: #c6f6d5;
            color: #22543d;
        }}
        
        .badge-warning {{
            background: #feebc8;
            color: #7c2d12;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏛️ Karnataka High Court Statistics</h1>
            <p class="subtitle">Daily Performance Dashboard - Bengaluru</p>
            <p class="subtitle">Last Updated: {latest_date}</p>
            
            <div class="disclaimer">
                <strong>📊 Data Tracking Notice:</strong> 
                Statistics are tracked from <strong>{TRACKING_START_DATE}</strong> onwards. 
                Case history shows listing dates from when tracking began, not original filing dates. 
                Historical cases filed before 2026 will show first listing date as when we first observed them in our system.
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Cases Scheduled Today</div>
                <div class="value">{daily_scheduled}</div>
            </div>
            
            <div class="stat-card">
                <div class="label">Cases Heard Today</div>
                <div class="value">{daily_heard}</div>
            </div>
            
            <div class="stat-card">
                <div class="label">Cases Not Reached</div>
                <div class="value">{daily_scheduled - daily_heard}</div>
            </div>
            
            <div class="stat-card">
                <div class="label">Overall Efficiency</div>
                <div class="value">{daily_efficiency:.1f}%</div>
                <div class="efficiency-bar">
                    <div class="efficiency-fill" style="width: {daily_efficiency}%"></div>
                </div>
            </div>
        </div>
        
        {generate_monthly_section(monthly) if monthly else ''}
        
        <div class="chart-container">
            <h2>📈 Weekly Efficiency Trend</h2>
            <canvas id="weeklyChart"></canvas>
        </div>
        
        <div class="judge-table">
            <h2>👨‍⚖️ Today's Judge Performance</h2>
            <table>
                <thead>
                    <tr>
                        <th>Judge Name</th>
                        <th>Court Hall</th>
                        <th>Scheduled</th>
                        <th>Heard</th>
                        <th>Not Reached</th>
                        <th>Efficiency</th>
                    </tr>
                </thead>
                <tbody>
                    {generate_judge_rows(judges)}
                </tbody>
            </table>
        </div>
        
        {generate_top_judges_section(top_judges) if top_judges else ''}
        
        <div class="footer">
            <p>Generated using Karnataka High Court Analytics Data</p>
            <p>Data sourced from official cause lists,case types and display board(30 sec frequency)</p>
        </div>
    </div>
    
    <script>
        // Weekly trend chart
        const ctx = document.getElementById('weeklyChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {weekly_dates},
                datasets: [{{
                    label: 'Efficiency %',
                    data: {weekly_efficiency},
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    tension: 0.4,
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        ticks: {{
                            callback: function(value) {{
                                return value + '%';
                            }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
    
    return html


def generate_monthly_section(monthly):
    """Generate monthly statistics section"""
    return f"""
        <div class="chart-container">
            <h2>📅 {monthly['month']} Summary</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="label">Working Days</div>
                    <div class="value">{monthly['days']}</div>
                </div>
                <div class="stat-card">
                    <div class="label">Total Scheduled</div>
                    <div class="value">{monthly['total_scheduled']}</div>
                </div>
                <div class="stat-card">
                    <div class="label">Total Heard</div>
                    <div class="value">{monthly['total_heard']}</div>
                </div>
                <div class="stat-card">
                    <div class="label">Month Efficiency</div>
                    <div class="value">{monthly['efficiency']:.1f}%</div>
                </div>
            </div>
        </div>
    """


def generate_judge_rows(judges):
    """Generate table rows for judges"""
    if not judges:
        return '<tr><td colspan="6" style="text-align: center;">No data available</td></tr>'
    
    rows = []
    for judge in judges:
        efficiency = judge['hearing_efficiency']
        badge_class = 'badge-success' if efficiency >= 70 else 'badge-warning'
        
        rows.append(f"""
            <tr>
                <td><strong>{judge['judge_name']}</strong></td>
                <td>{judge['court_hall']}</td>
                <td>{judge['cases_scheduled']}</td>
                <td>{judge['cases_heard']}</td>
                <td>{judge['cases_not_reached']}</td>
                <td>
                    <span class="badge {badge_class}">{efficiency:.1f}%</span>
                    <div class="efficiency-bar" style="margin-top: 5px;">
                        <div class="efficiency-fill" style="width: {efficiency}%"></div>
                    </div>
                </td>
            </tr>
        """)
    
    return '\n'.join(rows)


def generate_top_judges_section(top_judges):
    """Generate top judges section"""
    if not top_judges:
        return ''
    
    rows = []
    for i, judge in enumerate(top_judges[:10], 1):
        rows.append(f"""
            <tr>
                <td>{i}</td>
                <td><strong>{judge['judge_name']}</strong></td>
                <td>{judge['total_scheduled']}</td>
                <td>{judge['total_heard']}</td>
                <td>
                    <span class="badge badge-success">{judge['efficiency']:.1f}%</span>
                </td>
            </tr>
        """)
    
    return f"""
        <div class="judge-table" style="margin-top: 30px;">
            <h2>🏆 Top Performing Judges This Month</h2>
            <table>
                <thead>
                    <tr>
                        <th>Rank</th>
                        <th>Judge Name</th>
                        <th>Total Scheduled</th>
                        <th>Total Heard</th>
                        <th>Efficiency</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
    """


if __name__ == "__main__":
    generate_dashboard()
