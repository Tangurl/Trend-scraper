import os
import sys
import time
import json
import shutil
import argparse
import requests
from bs4 import BeautifulSoup
import gspread
from datetime import datetime, timezone, timedelta
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Timezone configurations (ICT = Indochina Time = UTC+7)
ICT_TZ = timezone(timedelta(hours=7))

# Project Base Directory (Dynamic for portability across machines)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Automation & Retention Configuration
LOOP_INTERVAL_MINUTES = 60  # Set to 0 or None to run once and exit, or >0 to repeat every X minutes
RETENTION_DAYS = 7          # Automatically delete Google Sheet entries older than X days (set 0 or None to disable)

# Spreadsheet config
SPREADSHEET_ID = ""
LOCAL_TOKEN_PATH = os.path.join(BASE_DIR, "token.json")
FALLBACK_TOKEN_PATH = ""
TOKEN_PATH = LOCAL_TOKEN_PATH if os.path.exists(LOCAL_TOKEN_PATH) else FALLBACK_TOKEN_PATH

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def scrape_google_trends():
    """Scrapes Google Trends Thailand for keywords and search volumes (Trending Now)."""
    url = "https://trends.google.com/trending?geo=TH&sort=search-volume"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"Fetching Google Trends from {url}...")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching Google Trends page: {e}")
        return []
        
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract keywords (div class="mZ3RIc") and search volume (div class="lqv0Cb")
    keyword_elements = soup.find_all(class_="mZ3RIc")
    volume_elements = soup.find_all(class_="lqv0Cb")
    
    keywords = [el.get_text(strip=True) for el in keyword_elements]
    volumes = [el.get_text(strip=True) for el in volume_elements]
    
    trends = []
    min_len = min(len(keywords), len(volumes))
    
    if min_len == 0:
        print("Warning: No trends data found on Google Trends page. Selectors might have changed.")
        return []
        
    for i in range(min_len):
        trends.append({
            "social": "Google Trends",
            "keyword": keywords[i],
            "volume": volumes[i],
            "freshness": "Past 24 hours"
        })
        
    print(f"Successfully scraped {len(trends)} items from Google Trends.")
    return trends

def scrape_google_explore_trends(gprop="youtube", platform_name="YouTube"):
    """Scrapes Google Trends Explore pages (e.g. YouTube or News search trends)."""
    base_dir = BASE_DIR
    yt_profile = os.path.join(base_dir, "chrome_profile_yt")
    
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--lang=en-US')
    options.add_argument('--accept-lang=en-US,en')
    options.add_argument(f"--user-data-dir={yt_profile}")
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    print(f"Launching Chrome for {platform_name}...")
    driver = webdriver.Chrome(options=options)
    target_url = f"https://trends.google.com/trends/explore?date=now%207-d&geo=TH&gprop={gprop}&hl=en"
    
    trends = []
    try:
        driver.execute_cdp_cmd('Emulation.setTimezoneOverride', {'timezoneId': 'Asia/Bangkok'})
        print(f"Navigating to {target_url}...")
        driver.get(target_url)
        time.sleep(5)
        
        # Close Google cookie consent if it appears
        try:
            consent_buttons = driver.find_elements(By.XPATH, (
                '//button[.//span[contains(text(), "Accept all") or contains(text(), "ยอมรับทั้งหมด") or '
                'contains(text(), "OK, got it") or contains(text(), "เข้าใจแล้ว") or '
                'contains(text(), "OK") or contains(text(), "ยอมรับ")]] | '
                '//button[contains(text(), "Accept all") or contains(text(), "ยอมรับทั้งหมด") or '
                'contains(text(), "OK") or contains(text(), "ยอมรับ")]'
            ))
            if consent_buttons:
                print("Google consent banner found. Clicking 'Accept all'...")
                driver.execute_script("arguments[0].click();", consent_buttons[0])
                time.sleep(3)
        except Exception as ce:
            print(f"Consent banner handler log: {ce}")
            
        # Scroll queries widget container into view with WebDriverWait
        print(f"Locating {platform_name} widget and scrolling it into view...")
        try:
            widget = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.widget-container:nth-child(2)'))
            )
            driver.execute_script('arguments[0].scrollIntoView();', widget)
        except Exception as we:
            print(f"Widget locator log: {we}")
            widget = driver.find_element(By.CSS_SELECTOR, 'div.widget-container:nth-child(2)')
            driver.execute_script('arguments[0].scrollIntoView();', widget)
        
        # Wait and retry logic to load container items
        success = False
        for attempt in range(1, 4):
            print(f"Attempt {attempt}: Waiting for {platform_name} widget items to load...")
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.widget-container:nth-child(2) .item'))
                )
                time.sleep(3)
                items = widget.find_elements(By.CLASS_NAME, 'item')
                if len(items) > 0:
                    success = True
                    break
            except Exception as e:
                print(f"Attempt {attempt} failed: {e}")
            
            if attempt < 3:
                print("Refreshing page...")
                driver.refresh()
                time.sleep(5)
                # Re-check consent banner on refresh
                try:
                    consent_buttons = driver.find_elements(By.XPATH, (
                        '//button[.//span[contains(text(), "Accept all") or contains(text(), "ยอมรับทั้งหมด") or '
                        'contains(text(), "OK, got it") or contains(text(), "เข้าใจแล้ว") or '
                        'contains(text(), "OK") or contains(text(), "ยอมรับ")]] | '
                        '//button[contains(text(), "Accept all") or contains(text(), "ยอมรับทั้งหมด") or '
                        'contains(text(), "OK") or contains(text(), "ยอมรับ")]'
                    ))
                    if consent_buttons:
                        driver.execute_script("arguments[0].click();", consent_buttons[0])
                        time.sleep(2)
                except Exception:
                    pass
                    
                try:
                    widget = driver.find_element(By.CSS_SELECTOR, 'div.widget-container:nth-child(2)')
                    driver.execute_script('arguments[0].scrollIntoView();', widget)
                except Exception:
                    pass
                
        if not success:
            print(f"Error: {platform_name} container failed to load after 3 attempts.")
            return []
            
        # Extract items across up to 5 pages
        for page_num in range(1, 6):
            print(f"Scraping {platform_name} Page {page_num}/5...")
            
            WebDriverWait(widget, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'item'))
            )
            
            items = widget.find_elements(By.CLASS_NAME, 'item')
            print(f"Found {len(items)} items on page {page_num}")
            
            for item in items:
                try:
                    kw = item.find_element(By.CSS_SELECTOR, '.label-text span').text.strip()
                except Exception:
                    kw = ""
                    
                try:
                    vol = item.find_element(By.CLASS_NAME, 'rising-value').text.strip()
                except Exception:
                    vol = ""
                    
                if kw:
                    clean_vol = vol.replace("+", "").replace("%", "").strip()
                    if clean_vol in ("ดาวรุ่งพุ่งแรง", "Breakout"):
                        clean_vol = "Breakout"
                        
                    trends.append({
                        "social": platform_name,
                        "keyword": kw,
                        "volume": clean_vol,
                        "freshness": "Past 7 days"
                    })
                    print(f" - {kw}: {clean_vol}")
                    
            if page_num < 5:
                next_btns = widget.find_elements(By.CLASS_NAME, 'arrow-right-active')
                if next_btns:
                    try:
                        driver.execute_script('arguments[0].click();', next_btns[0])
                        time.sleep(3)
                    except Exception as click_err:
                        print(f"Pagination failed to click on page {page_num}: {click_err}")
                        break
                else:
                    print(f"Pagination finished on page {page_num} (reached the last page).")
                    break
                    
    except Exception as ex:
        print(f"Error scraping {platform_name}: {ex}")
    finally:
        if driver:
            driver.quit()
    print(f"Successfully scraped {len(trends)} items from {platform_name}.")
    return trends

def scrape_youtube_trends():
    """Scrapes YouTube search trends from the Google Trends explore page."""
    return scrape_google_explore_trends(gprop="youtube", platform_name="YouTube")

def scrape_google_news_trends():
    """Scrapes Google News search trends from the Google Trends explore page."""
    return scrape_google_explore_trends(gprop="news", platform_name="Google News Search")

def scrape_x_trends():
    """Scrapes X (Twitter) search trends from trends24.in for Thailand."""
    url = "https://trends24.in/thailand/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"Fetching X Trends from {url}...")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8'
    except Exception as e:
        print(f"Error fetching X Trends page: {e}")
        return []
        
    soup = BeautifulSoup(response.text, 'html.parser')
    container = soup.select_one('div.list-container:nth-child(1)')
    
    if not container:
        print("Warning: div.list-container:nth-child(1) not found on trends24.in. Selector might have changed.")
        return []
        
    items = container.select('ol li')
    print(f"Found {len(items)} items on trends24.in list.")
    
    trends = []
    # Scrape only the top 25
    target_items = items[:25]
    
    for idx, item in enumerate(target_items):
        try:
            a_tag = item.select_one('a')
            span_tag = item.select_one('span.tweet-count')
            
            keyword = a_tag.text.strip() if a_tag else ""
            volume = span_tag.text.strip() if span_tag else "N/A"
            
            if not volume:
                volume = "N/A"
                
            if keyword:
                trends.append({
                    "social": "X",
                    "keyword": keyword,
                    "volume": volume,
                    "freshness": "Real-time"
                })
                print(f" - {keyword}: {volume}")
        except Exception as item_err:
            print(f"Error parsing trends24 item {idx+1}: {item_err}")
            
    print(f"Successfully scraped {len(trends)} items from X Trends.")
    return trends

def scrape_tiktok_trends():
    """Scrapes TikTok trending queries from the search popup using Playwright."""
    from playwright.sync_api import sync_playwright
    import os

    print("Launching Playwright for TikTok Trends...")
    trends = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--lang=en-US"]
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            # Navigate with retry logic to avoid transient network timeouts
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    print(f"Navigating to https://www.tiktok.com/ (attempt {attempt}/{max_retries})...")
                    page.goto("https://www.tiktok.com/", wait_until="domcontentloaded", timeout=45000)
                    break
                except Exception as goto_err:
                    if attempt == max_retries:
                        raise goto_err
                    print(f"Navigation attempt {attempt} failed: {goto_err}. Retrying in 5 seconds...")
                    page.wait_for_timeout(5000)
            page.wait_for_timeout(5000)

            # Press Escape twice to close any guide/tutorial or focus lock overlays
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)

            # Click the visible Search button/pill
            try:
                page.click('[data-e2e="nav-search"]', timeout=5000)
                print("Clicked Search button.")
            except Exception as e:
                print(f"nav-search click failed: {e}, trying text=Search")
                try:
                    page.click("text=Search", timeout=5000)
                    print("Clicked Search pill text.")
                except Exception as e2:
                    print(f"Fallback Search pill click failed: {e2}")

            page.wait_for_timeout(2000)
            # Focus the search input to trigger suggestions
            try:
                page.focus('input[type="search"]', timeout=5000)
                print("Search input focused.")
            except Exception as e:
                print(f"Focus failed: {e}")

            # Wait for suggestion items to appear
            try:
                page.wait_for_selector('li[data-e2e="search-transfer-guess-search-item"]', state="attached", timeout=10000)
                print("Suggestion items loaded.")
            except Exception as e:
                print(f"Suggestion wait error: {e}")

            page.wait_for_timeout(1000)
            items = page.query_selector_all('li[data-e2e="search-transfer-guess-search-item"]')
            print(f"Found {len(items)} raw suggestion items.")

            seen = set()
            for item in items:
                try:
                    svg = item.query_selector('svg[class*="css-lb03ns"]')
                    h4 = item.query_selector('h4')
                    text = (h4.text_content() if h4 else item.text_content() or "").strip()
                    if text and text not in seen:
                        seen.add(text)
                        trends.append({
                            "social": "TikTok",
                            "keyword": text,
                            "volume": "N/A",
                            "freshness": "Real-time"
                        })
                        print(f" - {'[trending]' if svg else '[popular]'} {text}")
                except Exception as item_err:
                    print(f"Item parse error: {item_err}")
            browser.close()
    except Exception as ex:
        print(f"Error scraping TikTok Trends: {ex}")

    print(f"Successfully scraped {len(trends)} items from TikTok.")
    return trends

def clean_volume_value(val):
    """Converts volume shorthand (K/M) to integers, removes symbols (+, %, commas), and maps N/A to None."""
    if not val:
        return None
    val_str = str(val).strip()
    if val_str.upper() in ("N/A", "NONE", "NULL", ""):
        return None
        
    # Remove symbols like +, %, and commas
    cleaned = val_str.replace("+", "").replace("%", "").replace(",", "").strip()
    
    # Process K and M suffixes
    if cleaned.upper().endswith("M"):
        try:
            return int(float(cleaned[:-1].strip()) * 1000000)
        except ValueError:
            pass
    elif cleaned.upper().endswith("K"):
        try:
            return int(float(cleaned[:-1].strip()) * 1000)
        except ValueError:
            pass
            
    # Try generic numeric conversions
    try:
        if "." in cleaned:
            return int(float(cleaned))
        return int(cleaned)
    except ValueError:
        return cleaned

def cleanup_old_sheet_entries(sheet, retention_days):
    """Deletes rows in the Google Sheet where the Date column is older than retention_days."""
    if not retention_days or retention_days <= 0:
        return
        
    try:
        all_rows = sheet.get_all_values()
        if not all_rows or len(all_rows) <= 1:
            return
            
        header = all_rows[0]
        rows = all_rows[1:]
        
        cutoff_date = datetime.now(ICT_TZ) - timedelta(days=retention_days)
        kept_rows = [header]
        deleted_count = 0
        
        for r in rows:
            date_str = r[0].strip() if r and len(r) > 0 else ""
            keep = True
            if date_str:
                try:
                    row_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ICT_TZ)
                    if row_date < cutoff_date:
                        keep = False
                except ValueError:
                    try:
                        row_date = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=ICT_TZ)
                        if row_date < cutoff_date:
                            keep = False
                    except ValueError:
                        pass
                        
            if keep:
                kept_rows.append(r)
            else:
                deleted_count += 1
                
        if deleted_count > 0:
            print(f"Cleaning up Google Sheet: Deleting {deleted_count} rows older than {retention_days} days...")
            sheet.clear()
            sheet.update(kept_rows)
            print(f"Cleanup complete. Retained {len(kept_rows) - 1} rows.")
        else:
            print(f"No rows older than {retention_days} days found in Google Sheet.")
            
    except Exception as e:
        print(f"Warning: Failed to cleanup old sheet entries: {e}")

def append_to_google_sheet(rows, start_time_str):
    """Appends the scraped rows to the designated Google Spreadsheet."""
    if not os.path.exists(TOKEN_PATH):
        print(f"Error: Credentials token.json not found at {TOKEN_PATH}.")
        sys.exit(1)
        
    try:
        print(f"Connecting to Google Sheets (Spreadsheet ID: {SPREADSHEET_ID})...")
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        
        # Refresh credentials if expired
        if creds.expired and creds.refresh_token:
            print("Google credentials expired. Refreshing token...")
            try:
                creds.refresh(Request())
                with open(TOKEN_PATH, 'w', encoding='utf-8') as f:
                    f.write(creds.to_json())
                print("Token refreshed and saved successfully.")
            except Exception as re:
                print(f"Warning: Failed to refresh and save token: {re}")
                
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        
        # Automatically clean up entries older than RETENTION_DAYS
        cleanup_old_sheet_entries(sheet, RETENTION_DAYS)
        
        # Prepare rows to append
        # Columns: Date, Social, Keyword, Search Volume, Freshness
        values_to_append = []
        for r in rows:
            values_to_append.append([
                start_time_str,
                r["social"],
                r["keyword"],
                clean_volume_value(r["volume"]),
                r["freshness"]
            ])
            
        print(f"Appending {len(values_to_append)} rows to Google Sheet '{sheet.title}'...")
        sheet.append_rows(values_to_append, value_input_option="USER_ENTERED")
        print("Successfully updated Google Sheets!")
        
    except Exception as e:
        print(f"Error writing to Google Sheets: {e}")
        sys.exit(1)

def main():
    while True:
        start_time_str = datetime.now(ICT_TZ).strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n==================================================")
        print(f"Scraping run started at: {start_time_str}")
        print(f"==================================================")
        
        # 1. Scrape Google Trends
        google_trends = scrape_google_trends()
        
        # 2. Scrape YouTube Trends
        youtube_trends = scrape_youtube_trends()
        
        # 3. Scrape Google News Search Trends
        google_news_trends = scrape_google_news_trends()
        
        # 4. Scrape X Trends
        x_trends = scrape_x_trends()
        
        # 5. Scrape TikTok Trends
        tiktok_trends = scrape_tiktok_trends()
        
        all_trends = google_trends + youtube_trends + google_news_trends + x_trends + tiktok_trends
        
        if all_trends:
            append_to_google_sheet(all_trends, start_time_str)
        else:
            print("No trends data was scraped from any platform. Google Sheets was not updated.")
            
        if not LOOP_INTERVAL_MINUTES or LOOP_INTERVAL_MINUTES <= 0:
            print("\nLOOP_INTERVAL_MINUTES is 0 or disabled. Single run completed.")
            break
            
        next_run = (datetime.now(ICT_TZ) + timedelta(minutes=LOOP_INTERVAL_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
        print(f"\nSleeping for {LOOP_INTERVAL_MINUTES} minutes until next run...")
        print(f"Next run scheduled for: {next_run} (ICT)")
        time.sleep(LOOP_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    main()
