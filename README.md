# Multi-Platform Trend Scraper

An automated Python data pipeline that aggregates trending topics, search volumes, and breakout queries across 5 platforms in Thailand—**Google Trends**, **YouTube**, **Google News Search**, **X (Twitter)**, and **TikTok**—and continuously synchronizes the cleaned data into Google Sheets.

---

## 📌 Supported Platforms & Scraping Methods

| Platform | Scope / Freshness | Collection Method | Key Details |
| :--- | :--- | :--- | :--- |
| **Google Trends** | Past 24 hours | Static HTTP (`requests` + `BeautifulSoup`) | Scrapes Thailand "Trending Now" directly from HTML to bypass rate limiting. |
| **YouTube** | Past 7 days | Headless Selenium (`webdriver.Chrome`) | Scrapes Google Trends Explore (`gprop=youtube`), handles consent popups, and paginates up to 5 pages. |
| **Google News Search** | Past 7 days | Headless Selenium (`webdriver.Chrome`) | Scrapes Google Trends Explore (`gprop=news`) for rising news search queries. |
| **X (Twitter)** | Real-time | Static HTTP (`requests` + `BeautifulSoup`) | Scrapes the top 25 real-time Thailand trends and tweet volumes via `trends24.in`. |
| **TikTok** | Real-time | Headless Playwright (`chromium`) | Automates search interaction on `tiktok.com` to capture trending and popular search suggestions. |

---

## 🚀 Key Features

- **Multi-Platform Coverage**: Scrapes across 5 major social and search ecosystems in a single automated run.
- **Search Volume Normalization**:
  - Automatically strips formatting symbols (`+`, `%`, `,`).
  - Converts unit multipliers into integer counts (e.g., `50K` $\rightarrow$ `50000`, `1.2M` $\rightarrow$ `1200000`).
  - Normalizes Thai breakout labels (e.g., translates `"ดาวรุ่งพุ่งแรง"` to `"Breakout"`).
  - Handles missing or `N/A` values gracefully as blank cells.
- **Automated Data Retention**:
  - Automatically prunes entries older than a configurable threshold (`RETENTION_DAYS = 7`) from Google Sheets on every run to prevent sheet bloat.
- **Continuous Execution**:
  - Built-in interval loop (`LOOP_INTERVAL_MINUTES = 60`) for hourly unattended runs, or single execution on demand.
- **Resilient Google Sheets Integration**:
  - Direct updates using `gspread` and Google OAuth credentials.
  - Automatically detects expired OAuth tokens in `token.json`, refreshes them, and persists the new token.
- **Sheet Maintenance Utility**:
  - Includes `clean_existing_sheet.py` to retroactively clean and standardize existing volume data in the spreadsheet.

---

## 📂 Google Sheets Schema

Data is appended with the following 5 columns:

| Column | Type | Example | Description |
| :--- | :--- | :--- | :--- |
| **Date** | Datetime String | `2026-10-01 14:00:00` | Run execution start timestamp in Indochina Time (ICT / UTC+7). |
| **Social** | String | `Google Trends`, `YouTube`, `Google News Search`, `X`, `TikTok` | Source platform name. |
| **Keyword** | String | `น้ำท่วมเชียงใหม่`, `#เลือกตั้ง` | Scraped trending query, topic, or hashtag. |
| **Search Volume** | Integer / String / Blank | `50000`, `180`, `Breakout`, `""` | Cleaned numeric volume count or breakout indicator. |
| **Freshness** | String | `Past 24 hours`, `Past 7 days`, `Real-time` | Temporal scope of the trend. |

---

## 🛠️ Prerequisites & Installation

### 1. Requirements
- **Python 3.9+**
- **Google Chrome** installed (for Selenium)
- Valid Google Cloud OAuth credentials (`token.json`) with Google Sheets and Google Drive API scopes enabled.

### 2. Install Python Dependencies
```bash
pip install requests beautifulsoup4 gspread google-auth selenium playwright
```

### 3. Install Playwright Browsers
Install the Chromium browser binary required for TikTok scraping:
```bash
playwright install chromium
```

---

## ⚙️ Configuration

Open `trend_scraper.py` to configure project settings:

```python
# Automation & Retention Settings
LOOP_INTERVAL_MINUTES = 60  # Set to >0 to repeat every X minutes, or 0 / None to run once and exit
RETENTION_DAYS = 7          # Automatically delete entries older than X days (set 0 to disable)

# Google Spreadsheet Settings
SPREADSHEET_ID = "YOUR_SPREADSHEET_ID"
LOCAL_TOKEN_PATH = os.path.join(BASE_DIR, "token.json")
```

### Google OAuth Credentials (`token.json`)
Ensure your authorized Google OAuth `token.json` is located either in the project root (`token.json`) or in your configured fallback path. The required OAuth scopes are:
- `https://www.googleapis.com/auth/spreadsheets`
- `https://www.googleapis.com/auth/drive`

---

## 🖥️ Usage

### Run the Main Scraper
```bash
python trend_scraper.py
```
The scraper will:
1. Fetch Google Trends Thailand (Past 24 hours).
2. Launch Selenium to fetch YouTube Trends (Past 7 days).
3. Launch Selenium to fetch Google News Search Trends (Past 7 days).
4. Fetch real-time X (Twitter) Trends Thailand via Trends24.
5. Launch Playwright to scrape real-time TikTok search suggestions.
6. Connect to Google Sheets, prune entries older than 7 days, and append the latest dataset.
7. If `LOOP_INTERVAL_MINUTES > 0`, sleep until the next scheduled interval.

### Run One-Time Historical Sheet Cleanup
To clean up unformatted numbers, suffixes (`K`/`M`), or symbols in already-existing Google Sheet rows:
```bash
python clean_existing_sheet.py
```

---

## 📁 Repository Structure

```text
Trend-scraper/
├── trend_scraper.py         # Main multi-platform scraper & Google Sheets sync pipeline
├── clean_existing_sheet.py   # Maintenance script to clean historical spreadsheet data
├── README.md                 # Project documentation and setup guide
└── .gitignore                # Git ignore rules for browser profiles, credentials, and OS caches
```
