import os
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
load_dotenv()

# Gemini Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Google Sheets Config
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
# Service account can be loaded via a path to json file or raw json string from env
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

def validate_config():
    """Validates that critical configurations are present."""
    warnings = []
    if not GEMINI_API_KEY:
        warnings.append("GEMINI_API_KEY is missing. AI filtering will not work.")
    if not SPREADSHEET_ID:
        warnings.append("SPREADSHEET_ID is missing. Google Sheets read/write will fail.")
    if not GOOGLE_SERVICE_ACCOUNT_JSON and not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
        warnings.append("Neither GOOGLE_SERVICE_ACCOUNT_JSON nor service_account.json exists. Sheets authentication will fail.")
    return warnings
