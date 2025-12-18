# Karnataka High Court Case Tracker

A comprehensive system to track, analyze, and compare scheduled vs. heard cases at Karnataka High Court, Bengaluru. Automatically scrapes court display boards, parses cause list PDFs, and generates performance analytics for judges and advocates.

---

## 🎯 Features

### Data Collection
- **Real-time Display Board Scraping** - Tracks cases being heard in court halls
- **Daily Cause List Parsing** - Extracts scheduled cases from PDF
- **End-of-Day Analysis** - Compares scheduled vs. heard cases

### Analytics & Insights
- ✅ Judge performance metrics (hearing efficiency, disposal rates)
- ✅ Advocate statistics (appearance frequency, success rates)
- ✅ Case history tracking (listings, hearings, pending duration)
- ✅ Success/failure rate analysis per court hall
- ✅ Identify cases listed but never heard
- ✅ Track cases heard maximum times
- ✅ Most favored advocates by disposal rate

### Storage Options
- **Supabase (PostgreSQL)** - Cloud database with real-time queries
- **CSV Files** - Local file-based storage (lightweight alternative)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Flow                                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  9:00 AM  → Parse Cause List PDF → cause_list_cases         │
│             (Scheduled cases)                                │
│                                                               │
│  10:25 AM → Display Board Scraper → heard_cases             │
│  - 5:30 PM  (Every 30 seconds)                              │
│                                                               │
│  6:00 PM  → EOD Analysis → Statistics Tables                │
│             (Compare & Analyze)                              │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Database Schema

### Core Tables
1. **`cause_list_cases`** - Morning scheduled cases from PDF
2. **`heard_cases`** - Real-time cases from display board
3. **`case_status_tracker`** - Daily comparison (scheduled vs heard)
4. **`advocate_statistics`** - Daily advocate performance
5. **`judge_statistics`** - Daily judge efficiency metrics
6. **`case_history`** - Long-term case tracking

See [Database Schema Documentation](docs/DATABASE.md) for detailed schema.

---

## 🚀 Deployment Options

### Option 1: GitHub Actions (Automated Cloud)
- ✅ Fully automated, no local infrastructure
- ✅ Unlimited compute (public repo)
- ⚠️ 5-minute minimum interval (not true 30-second scraping)
- ⚠️ VM startup overhead (~30-60 seconds per run)

### Option 2: Local macOS (Recommended)
- ✅ True 30-second intervals with LaunchAgent/cron
- ✅ No startup overhead
- ✅ Full control over timing
- ⚠️ Requires Mac to be online during court hours

### Option 3: Hybrid (Best of Both)
- ✅ GitHub Actions: Morning PDF parsing + EOD analysis
- ✅ Local Mac: Real-time display board scraping
- ✅ Combines cloud automation with precise timing

---

## 📋 Prerequisites

- Python 3.9+
- Supabase account (free tier sufficient)
- GitHub account (for GitHub Actions deployment)
- macOS/Linux (for local deployment)

---

## 🛠️ Technology Stack

**Backend:**
- Python 3.11
- Beautiful Soup 4 (HTML parsing)
- PyPDF2 (PDF parsing)
- Requests (HTTP client)
- Supabase Python Client

**Database:**
- PostgreSQL (via Supabase)
- Alternative: CSV files

**Infrastructure:**
- GitHub Actions (cloud automation)
- LaunchAgent/Cron (local scheduling)

---

## 📁 Project Structure

```
court-scraper/
├── .github/
│   └── workflows/
│       ├── scrape-display-board.yml    # Display board scraper
│       ├── parse-cause-list.yml        # Morning PDF parser
│       └── eod-analysis.yml            # Evening analysis
├── scripts/
│   ├── display_board_scraper.py        # Real-time scraper
│   ├── cause_list_parser.py            # PDF parser
│   ├── eod_processor.py                # EOD statistics
│   └── query_court_data.py             # Query utility
├── docs/
│   ├── DATABASE.md                     # Schema documentation
│   └── QUERIES.md                      # SQL query examples
├── requirements.txt                    # Python dependencies
├── .env.example                        # Environment variables template
├── README.md                           # This file
└── INSTALL.md                          # Installation guide
```

---

## 🔍 Sample Queries

### Cases Pending (Listed but Not Heard)
```sql
SELECT cl.case_number, cl.petitioner_name, cl.petitioner_advocate
FROM cause_list_cases cl
LEFT JOIN heard_cases hc ON cl.case_number = hc.case_number 
    AND cl.date = hc.date
WHERE cl.date = '2025-12-17'
  AND hc.id IS NULL;
```

### Judge Performance
```sql
SELECT judge_name, court_hall,
       AVG(hearing_efficiency) as avg_efficiency,
       SUM(cases_heard) as total_heard
FROM judge_statistics
WHERE date >= '2025-12-01'
GROUP BY judge_name, court_hall
ORDER BY avg_efficiency DESC;
```

### Most Frequent Advocate
```sql
SELECT advocate_name, 
       SUM(cases_scheduled) as total_cases,
       AVG(hearing_rate) as avg_hearing_rate
FROM advocate_statistics
WHERE date >= '2025-12-01'
GROUP BY advocate_name
ORDER BY total_cases DESC
LIMIT 10;
```

See [QUERIES.md](docs/QUERIES.md) for more examples.

---

## 📈 Storage Requirements

### Supabase (PostgreSQL)
- **Daily data:** ~1 MB
- **Monthly:** ~30 MB
- **Yearly:** ~360 MB
- **5 years:** ~1.8 GB
- ✅ Free tier: 500 MB (sufficient for 1+ year)

### CSV (Local)
- **Daily:** ~100 KB per CSV file
- **Yearly:** ~35 MB
- **5 years:** ~175 MB

---

## 🔐 Environment Variables

Required environment variables:

```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=your-anon-key-here
```

---

## 📊 Dashboard & Visualization

Query scripts provided for:
- Daily success rates
- Judge performance comparison
- Advocate ranking by cases
- Long-term trends
- Case disposal analytics

Future: Web dashboard with charts and real-time updates.

---

## 🐛 Troubleshooting

### Display Board Scraper Issues
- **No records found:** Check if court website is accessible
- **HTML parsing errors:** Website structure may have changed
- **Timeout errors:** Network connectivity issues

### PDF Parser Issues
- **PDF download fails:** Check URL and court website status
- **Parsing errors:** PDF format may have changed
- **Missing data:** Regex patterns need adjustment

### Database Issues
- **Connection errors:** Verify Supabase credentials
- **Insert failures:** Check table schema matches
- **Duplicate errors:** Unique constraints triggered

See [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for detailed solutions.

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/your-username/court-scraper/issues)
- **Documentation:** [Wiki](https://github.com/your-username/court-scraper/wiki)

---

## 🙏 Acknowledgments

- Karnataka High Court for public data access
- Supabase for database infrastructure
- GitHub for automation platform

---

## 📅 Roadmap

- [ ] Web dashboard with real-time updates
- [ ] Email/SMS notifications for case hearings
- [ ] Multi-court support (other Karnataka courts)
- [ ] Mobile app for lawyers and litigants
- [ ] Machine learning predictions for case outcomes
- [ ] Historical data analysis (5+ years)
- [ ] Export reports to PDF/Excel
- [ ] API for third-party integrations

---

## ⚖️ Disclaimer

This project is for educational and informational purposes only. The data is sourced from publicly available information on the Karnataka High Court website. The accuracy of scraped data depends on the court website's availability and format. This tool is not affiliated with or endorsed by the Karnataka High Court.

---

**Version:** 1.0.0  
**Last Updated:** December 2025  
**Status:** Active Development

---

