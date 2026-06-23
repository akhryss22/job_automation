import json
import logging
import gspread
from google.oauth2.service_account import Credentials
import config

logger = logging.getLogger(__name__)

# Scope for Google Sheets and Drive APIs
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_gspread_client():
    """Authenticates and returns a gspread client."""
    if config.GOOGLE_SERVICE_ACCOUNT_JSON:
        try:
            creds_info = json.loads(config.GOOGLE_SERVICE_ACCOUNT_JSON)
            creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
            return gspread.authorize(creds)
        except Exception as e:
            logger.error(f"Failed to authenticate using raw JSON service account: {e}")
            raise e
    else:
        try:
            creds = Credentials.from_service_account_file(config.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES)
            return gspread.authorize(creds)
        except Exception as e:
            logger.error(f"Failed to authenticate using file {config.GOOGLE_SERVICE_ACCOUNT_FILE}: {e}")
            raise e

class SheetHandler:
    def __init__(self):
        self.client = get_gspread_client()
        self.spreadsheet = self.client.open_by_key(config.SPREADSHEET_ID)
        # Select first worksheet as default target
        self.worksheet = self.spreadsheet.get_worksheet(0)

    def get_companies_to_scrape(self):
        """
        Reads the spreadsheet and returns target companies and their URLs.
        Assumes headers:
        Column A: Company Name
        Column B: Scrape URL
        
        Returns:
            list of dicts: [{'row': int, 'company': str, 'url': str}]
        """
        all_values = self.worksheet.get_all_values()
        if not all_values:
            return []

        # Find header indices (assuming row 1 is header)
        headers = [h.strip().lower() for h in all_values[0]]
        
        # Default column indices if headers aren't explicitly named
        company_idx = 0
        url_idx = 1
        
        # Try to find headers dynamically
        for idx, h in enumerate(headers):
            if "company" in h:
                company_idx = idx
            elif "url" in h or "link" in h:
                url_idx = idx

        companies = []
        # Row 1 is header, so start from 2 (1-indexed index = idx + 1)
        for idx, row in enumerate(all_values[1:], start=2):
            if len(row) > max(company_idx, url_idx):
                company_name = row[company_idx].strip()
                url = row[url_idx].strip()
                if company_name and url:
                    companies.append({
                        "row": idx,
                        "company": company_name,
                        "url": url
                    })
        return companies

    def update_chosen_roles(self, row_number, caption, column_letter="C"):
        """
        Updates the 'Chosen Roles' caption column for a specific company row.
        """
        try:
            # We can also dynamically find Column C or the header "Chosen Roles"
            # Let's write to Column C by default
            self.worksheet.update(range_name=f"{column_letter}{row_number}", values=[[caption]])
            logger.info(f"Updated row {row_number} with roles caption.")
        except Exception as e:
            logger.error(f"Error updating sheet row {row_number}: {e}")
            raise e

    def init_headers_if_empty(self):
        """Initializes headers on an empty worksheet."""
        all_values = self.worksheet.get_all_values()
        if not all_values:
            self.worksheet.update(range_name="A1:C1", values=[["Company Name", "Scrape URL", "Chosen Roles"]])
            logger.info("Initialized default headers: Company Name, Scrape URL, Chosen Roles")
