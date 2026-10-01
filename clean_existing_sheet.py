import os
import sys
import gspread
from google.oauth2.credentials import Credentials
from trend_scraper import clean_volume_value, TOKEN_PATH, SCOPES, SPREADSHEET_ID

def main():
    if not os.path.exists(TOKEN_PATH):
        print(f"Error: Credentials token.json not found at {TOKEN_PATH}.")
        sys.exit(1)
        
    try:
        print("Connecting to Google Sheets...")
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        
        print("Fetching all values from sheet...")
        all_rows = sheet.get_all_values()
        if not all_rows:
            print("Sheet is empty.")
            return
            
        header = all_rows[0]
        print(f"Loaded {len(all_rows)} rows. Header: {header}")
        
        # Verify Search Volume is the 4th column (index 3)
        vol_idx = 3
        if len(header) > vol_idx and "volume" in header[vol_idx].lower():
            print(f"Confirmed volume column at index {vol_idx}")
        else:
            # Fallback dynamic matching if column headers ever shift
            for idx, col in enumerate(header):
                if "volume" in col.lower():
                    vol_idx = idx
                    print(f"Found volume column dynamic matching at index {vol_idx}")
                    break
            else:
                print("Error: Could not find 'Search Volume' column.")
                sys.exit(1)
        
        cleaned_count = 0
        updated_rows = [header]
        
        for row in all_rows[1:]:
            original_val = row[vol_idx] if len(row) > vol_idx else ""
            cleaned_val = clean_volume_value(original_val)
            
            # Map None to empty cell string
            if cleaned_val is None:
                cleaned_val = ""
            else:
                cleaned_val = str(cleaned_val)
                
            if len(row) > vol_idx:
                row[vol_idx] = cleaned_val
            else:
                # If row is shorter, expand it
                while len(row) <= vol_idx:
                    row.append("")
                row[vol_idx] = cleaned_val
                
            if str(original_val) != str(cleaned_val):
                cleaned_count += 1
                
            updated_rows.append(row)
            
        print(f"Cleaned {cleaned_count} values. Writing updates back to Google Sheet...")
        
        # In gspread 6.0+, Worksheet.update takes values as positional argument
        sheet.update(updated_rows)
        print("Google Sheet successfully updated and cleaned!")
        
    except Exception as e:
        print(f"Error updating Google Sheet: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
