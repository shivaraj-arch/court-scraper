# INSTALL.md

# Installation Guide - Karnataka High Court Case Tracker

Complete installation instructions for all deployment options.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Supabase Setup](#supabase-setup)
3. [GitHub Actions Deployment](#github-actions-deployment)
4. [Local macOS Deployment](#local-macos-deployment)
5. [Hybrid Deployment](#hybrid-deployment)
6. [Verification & Testing](#verification--testing)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software
```bash
# Python 3.9 or higher
python3 --version

# Git
git --version

# Homebrew (macOS only)
brew --version
```

### Required Accounts
- **Supabase Account** - Sign up at https://supabase.com (free tier)
- **GitHub Account** - Sign up at https://github.com (free)

---

## Supabase Setup

### Step 1: Create Supabase Project

1. Go to https://supabase.com
2. Click **"New Project"**
3. Fill in details:
   - **Name:** Karnataka Court Tracker
   - **Database Password:** (choose strong password)
   - **Region:** Asia South (Mumbai) or Southeast Asia (Singapore)
4. Click **"Create new project"**
5. Wait 2-3 minutes for provisioning

### Step 2: Create Database Tables

1. In Supabase Dashboard, go to **SQL Editor**
2. Click **"New query"**
3. Copy and paste the following SQL:

```sql
-- Table 1: Cause List Cases (Scheduled)
CREATE TABLE cause_list_cases (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    court_hall INTEGER NOT NULL,
    list_number INTEGER NOT NULL,
    sl_no INTEGER NOT NULL,
    case_number TEXT NOT NULL,
    case_type TEXT,
    case_year INTEGER,
    judge_name TEXT NOT NULL,
    co_judge_name TEXT,
    petitioner_name TEXT,
    petitioner_advocate TEXT,
    respondent_name TEXT,
    respondent_advocate TEXT,
    all_advocates TEXT[],
    case_category TEXT,
    interim_applications TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, court_hall, case_number)
);

CREATE INDEX idx_cl_date ON cause_list_cases(date);
CREATE INDEX idx_cl_court_hall ON cause_list_cases(court_hall);
CREATE INDEX idx_cl_case_number ON cause_list_cases(case_number);
CREATE INDEX idx_cl_judge ON cause_list_cases(judge_name);
CREATE INDEX idx_cl_advocates ON cause_list_cases USING GIN(all_advocates);

-- Table 2: Heard Cases (From Display Board)
CREATE TABLE heard_cases (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    court_hall INTEGER NOT NULL,
    list_number INTEGER NOT NULL,
    case_number TEXT NOT NULL,
    first_heard_at TIMESTAMPTZ NOT NULL,
    last_heard_at TIMESTAMPTZ NOT NULL,
    total_appearances INTEGER DEFAULT 1,
    status TEXT DEFAULT 'in_progress',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, court_hall, case_number)
);

CREATE INDEX idx_hc_date ON heard_cases(date);
CREATE INDEX idx_hc_court_hall ON heard_cases(court_hall);
CREATE INDEX idx_hc_case_number ON heard_cases(case_number);
CREATE INDEX idx_hc_status ON heard_cases(status);

-- Table 3: Case Status Tracker
CREATE TABLE case_status_tracker (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    court_hall INTEGER NOT NULL,
    case_number TEXT NOT NULL,
    was_scheduled BOOLEAN DEFAULT FALSE,
    was_heard BOOLEAN DEFAULT FALSE,
    outcome TEXT,
    cause_list_id BIGINT REFERENCES cause_list_cases(id),
    heard_case_id BIGINT REFERENCES heard_cases(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, court_hall, case_number)
);

CREATE INDEX idx_cst_date ON case_status_tracker(date);
CREATE INDEX idx_cst_outcome ON case_status_tracker(outcome);

-- Table 4: Advocate Statistics
CREATE TABLE advocate_statistics (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    court_hall INTEGER,
    advocate_name TEXT NOT NULL,
    cases_scheduled INTEGER DEFAULT 0,
    cases_heard INTEGER DEFAULT 0,
    cases_disposed INTEGER DEFAULT 0,
    cases_adjourned INTEGER DEFAULT 0,
    hearing_rate DECIMAL(5,2),
    disposal_rate DECIMAL(5,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, court_hall, advocate_name)
);

CREATE INDEX idx_adv_date ON advocate_statistics(date);
CREATE INDEX idx_adv_name ON advocate_statistics(advocate_name);

-- Table 5: Judge Statistics
CREATE TABLE judge_statistics (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    court_hall INTEGER NOT NULL,
    judge_name TEXT NOT NULL,
    cases_scheduled INTEGER DEFAULT 0,
    cases_heard INTEGER DEFAULT 0,
    cases_disposed INTEGER DEFAULT 0,
    cases_adjourned INTEGER DEFAULT 0,
    cases_not_reached INTEGER DEFAULT 0,
    hearing_efficiency DECIMAL(5,2),
    disposal_efficiency DECIMAL(5,2),
    court_start_time TIME,
    court_end_time TIME,
    working_hours DECIMAL(5,2),
    cases_per_hour DECIMAL(5,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, court_hall, judge_name)
);

CREATE INDEX idx_judge_date ON judge_statistics(date);
CREATE INDEX idx_judge_name ON judge_statistics(judge_name);

-- Table 6: Case History
CREATE TABLE case_history (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT NOT NULL,
    first_listed_date DATE,
    last_listed_date DATE,
    total_listings INTEGER DEFAULT 0,
    total_hearings INTEGER DEFAULT 0,
    current_status TEXT,
    disposed_date DATE,
    days_pending INTEGER,
    hearing_to_listing_ratio DECIMAL(5,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(case_number)
);

CREATE INDEX idx_ch_case_number ON case_history(case_number);
CREATE INDEX idx_ch_status ON case_history(current_status);
```

4. Click **"Run"**
5. Verify: Go to **Table Editor** → You should see 6 tables

### Step 3: Get API Credentials

1. In Supabase Dashboard, go to **Settings** → **API**
2. Copy these values (you'll need them later):
   - **Project URL:** `https://xxxxx.supabase.co`
   - **anon public key:** `eyJhbGc...` (long string)

---

## GitHub Actions Deployment

### Step 1: Create GitHub Repository

```bash
# Clone or create new repository
git clone https://github.com/YOUR_USERNAME/court-scraper.git
cd court-scraper

# Or create new
mkdir court-scraper
cd court-scraper
git init
```

### Step 2: Create Project Structure

```bash
# Create directories
mkdir -p .github/workflows scripts docs

# Create files (copy content from artifacts)
touch .github/workflows/scrape-display-board.yml
touch .github/workflows/parse-cause-list.yml
touch .github/workflows/eod-analysis.yml
touch scripts/display_board_scraper.py
touch scripts/cause_list_parser.py
touch scripts/eod_processor.py
touch requirements.txt
touch README.md
touch INSTALL.md
```

### Step 3: Copy Script Content

Copy the content from the artifacts provided earlier:
- All workflow YAML files go in `.github/workflows/`
- All Python scripts go in `scripts/`
- `requirements.txt` content:

```
requests==2.31.0
beautifulsoup4==4.12.2
supabase==2.3.4
PyPDF2==3.0.1
```

### Step 4: Create .gitignore

```bash
cat > .gitignore << 'EOF'
*.log
*.pyc
__pycache__/
.env
.DS_Store
venv/
*.csv
court_data/
EOF
```

### Step 5: Push to GitHub

```bash
git add .
git commit -m "Initial commit: Court scraper system"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/court-scraper.git
git push -u origin main
```

### Step 6: Add GitHub Secrets

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**
4. Add these secrets:
   - **Name:** `SUPABASE_URL`  
     **Value:** Your Supabase project URL
   - **Name:** `SUPABASE_KEY`  
     **Value:** Your Supabase anon key
5. Click **"Add secret"** for each

### Step 7: Enable GitHub Actions

1. Go to **Actions** tab in your repository
2. Click **"I understand my workflows, go ahead and enable them"**
3. You should see 3 workflows listed

### Step 8: Test Workflows

1. Click on **"Parse Cause List"** workflow
2. Click **"Run workflow"** → **"Run workflow"**
3. Wait for completion (should take ~1 minute)
4. Check logs for any errors
5. Verify data in Supabase: Go to Supabase → **Table Editor** → `cause_list_cases`

---

## Local macOS Deployment

### Step 1: Install Dependencies

```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3
brew install python3

# Create project directory
mkdir ~/court-scraper
cd ~/court-scraper

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install requests beautifulsoup4 supabase PyPDF2
```

### Step 2: Set Environment Variables

```bash
# Option A: Add to ~/.zshrc (permanent)
echo 'export SUPABASE_URL="https://xxxxx.supabase.co"' >> ~/.zshrc
echo 'export SUPABASE_KEY="your-anon-key-here"' >> ~/.zshrc
source ~/.zshrc

# Option B: Create .env file
cat > .env << 'EOF'
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=your-anon-key-here
EOF

# If using .env, install python-dotenv
pip install python-dotenv
```

### Step 3: Copy Scripts

Copy Python scripts from the artifacts to `~/court-scraper/scripts/`

### Step 4: Create LaunchAgent (for Display Board Scraper)

```bash
# Create LaunchAgent plist
cat > ~/Library/LaunchAgents/com.court.scraper.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.court.scraper</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>$HOME/court-scraper/scripts/display_board_scraper.py</string>
    </array>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>SUPABASE_URL</key>
        <string>https://xxxxx.supabase.co</string>
        <key>SUPABASE_KEY</key>
        <string>your-anon-key-here</string>
    </dict>
    
    <key>WorkingDirectory</key>
    <string>$HOME/court-scraper</string>
    
    <key>StartInterval</key>
    <integer>30</integer>
    
    <key>StandardOutPath</key>
    <string>$HOME/court-scraper/logs/scraper_out.log</string>
    
    <key>StandardErrorPath</key>
    <string>$HOME/court-scraper/logs/scraper_err.log</string>
</dict>
</plist>
EOF

# Replace $HOME with actual path
sed -i '' "s|\$HOME|$HOME|g" ~/Library/LaunchAgents/com.court.scraper.plist

# Create logs directory
mkdir -p ~/court-scraper/logs

# Load LaunchAgent
launchctl load ~/Library/LaunchAgents/com.court.scraper.plist

# Check status
launchctl list | grep court.scraper
```

### Step 5: Schedule Other Scripts with Cron

```bash
# Edit crontab
crontab -e

# Add these lines:
# Parse cause list at 9 AM daily
30 3 * * * cd $HOME/court-scraper && /usr/local/bin/python3 scripts/cause_list_parser.py >> logs/parser.log 2>&1

# EOD analysis at 6 PM daily
30 12 * * * cd $HOME/court-scraper && /usr/local/bin/python3 scripts/eod_processor.py >> logs/eod.log 2>&1
```

---

## Hybrid Deployment

Combine the best of both:
- **Local Mac:** Display board scraping (true 30-second intervals)
- **GitHub Actions:** Morning PDF parsing + EOD analysis

### Setup Steps

1. **Complete Local macOS Deployment** (Steps 1-5 above)
   - This handles display board scraping every 30 seconds

2. **Complete GitHub Actions Deployment** (Steps 1-7)
   - **Disable** the display board workflow in GitHub Actions
   - Keep only `parse-cause-list.yml` and `eod-analysis.yml` active

3. **Disable Local LaunchAgent** for cause list and EOD:
   ```bash
   # Remove cron jobs (if added)
   crontab -e
   # Delete the cause list and EOD cron lines
   ```

**Result:** 
- GitHub Actions runs morning PDF parser (9 AM) and EOD analysis (6 PM)
- Your Mac runs display board scraper every 30 seconds during court hours

---

## Verification & Testing

### Test Supabase Connection

```python
# Create test_connection.py
from supabase import create_client
import os

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    result = supabase.table('cause_list_cases').select("count", count='exact').execute()
    print(f"✅ Connected! Total records: {result.count}")
except Exception as e:
    print(f"❌ Connection failed: {e}")
```

```bash
python3 test_connection.py
```

### Test Display Board Scraper

```bash
cd ~/court-scraper
python3 scripts/display_board_scraper.py
```

Check logs and Supabase `heard_cases` table.

### Test Cause List Parser

```bash
python3 scripts/cause_list_parser.py
```

Check Supabase `cause_list_cases` table.

### Test EOD Processor

```bash
python3 scripts/eod_processor.py
```

Check Supabase statistics tables.

### Monitor GitHub Actions

1. Go to GitHub repo → **Actions** tab
2. Click on a workflow run
3. View real-time logs
4. Check for errors

### Query Data in Supabase

```sql
-- Check today's scheduled cases
SELECT * FROM cause_list_cases WHERE date = CURRENT_DATE;

-- Check today's heard cases
SELECT * FROM heard_cases WHERE date = CURRENT_DATE;

-- Check statistics
SELECT * FROM judge_statistics WHERE date = CURRENT_DATE;
```

---

## Troubleshooting

### Issue: Python module not found

```bash
# Ensure you're in virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Supabase connection fails

```bash
# Verify credentials
echo $SUPABASE_URL
echo $SUPABASE_KEY

# Test connection manually
python3 test_connection.py
```

### Issue: LaunchAgent not running

```bash
# Check if loaded
launchctl list | grep court.scraper

# View logs
tail -f ~/court-scraper/logs/scraper_out.log
tail -f ~/court-scraper/logs/scraper_err.log

# Reload if needed
launchctl unload ~/Library/LaunchAgents/com.court.scraper.plist
launchctl load ~/Library/LaunchAgents/com.court.scraper.plist
```

### Issue: GitHub Actions workflow fails

1. Check workflow logs in Actions tab
2. Verify secrets are set correctly
3. Check Python script syntax
4. Test scripts locally first

### Issue: PDF parsing fails

- Verify PDF URL is accessible
- Check PDF format hasn't changed
- Update regex patterns if needed

### Issue: No data appearing in Supabase

1. Check table permissions (should be public for inserts)
2. Verify data types match schema
3. Check for unique constraint violations
4. Review error logs

---

## Next Steps

After successful installation:

1. **Monitor for 24 hours** to ensure all workflows run correctly
2. **Review data quality** in Supabase tables
3. **Run sample queries** to verify analytics
4. **Set up alerts** for failures (optional)
5. **Create dashboard** for visualization (future)

---

## Support

- **GitHub Issues:** Report bugs and request features
- **Documentation:** Check README.md for usage
- **Logs:** Always check logs first when troubleshooting

---

**Installation complete!** Your court scraper should now be running automatically.
