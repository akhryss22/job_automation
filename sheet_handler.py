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

    def get_all_worksheets(self):
        """Returns all worksheet tabs in the spreadsheet."""
        return self.spreadsheet.worksheets()

    def get_companies_to_scrape(self, worksheet):
        """
        Reads a worksheet tab and returns companies + optional URLs.
        Column A: Company Name (required)
        Column B: URL (optional — if missing, LinkedIn search by name is used)
        Returns: list of dicts: [{'row': int, 'company': str, 'url': str or None}]
        """
        all_values = worksheet.get_all_values()
        if not all_values:
            return []

        headers = [h.strip().lower() for h in all_values[0]]

        company_idx = 0
        url_idx = 1

        for idx, h in enumerate(headers):
            if "company" in h:
                company_idx = idx
            elif "url" in h or "link" in h:
                url_idx = idx

        companies = []
        for idx, row in enumerate(all_values[1:], start=2):
            if len(row) > company_idx:
                company_name = row[company_idx].strip()
                # URL is optional — blank means LinkedIn search by name
                url = row[url_idx].strip() if len(row) > url_idx else ""
                if company_name:
                    companies.append({
                        "row": idx,
                        "company": company_name,
                        "url": url or None  # None = no URL, use LinkedIn search
                    })
        return companies

    def update_chosen_roles(self, worksheet, row_number, caption, column_letter="C"):
        """Updates the matched roles cell for a specific company row."""
        try:
            worksheet.update(range_name=f"{column_letter}{row_number}", values=[[caption]])
            logger.info(f"Updated row {row_number} with roles caption.")
        except Exception as e:
            logger.error(f"Error updating sheet row {row_number}: {e}")
            raise e

    def init_headers_if_empty(self, worksheet):
        """Initializes headers on an empty worksheet tab."""
        all_values = worksheet.get_all_values()
        if not all_values:
            worksheet.update(range_name="A1:C1", values=[["Company Name", "Scrape URL", "Chosen Roles"]])
            logger.info(f"Initialized default headers on tab: {worksheet.title}")
