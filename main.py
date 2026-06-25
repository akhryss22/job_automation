import logging
import sys
import config
from sheet_handler import SheetHandler
import scraper
import job_filter

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("job_tracker")

# Tabs to skip entirely (case-insensitive partial match)
SKIP_TAB_KEYWORDS = ["readme", "instructions", "about", "guide", "non-hiring", "non hiring"]


def process_hiring_partners_tab(sheet, worksheet):
    """Processes a hiring-partners tab: reads company list, scrapes each, writes results."""
    companies = sheet.get_companies_to_scrape(worksheet)
    if not companies:
        logger.info(f"No companies found in tab '{worksheet.title}'. Skipping.")
        return

    logger.info(f"Tab '{worksheet.title}': {len(companies)} companies to process.")
    matched_count = 0

    for item in companies:
        row = item["row"]
        company = item["company"]
        url = item["url"]

        logger.info(f"Processing row {row}: {company} ({url or 'no URL'})")

        try:
            scrape_result = scraper.get_jobs_for_company(company, url)

            jobs = []
            if scrape_result["type"] == "jobs_list":
                jobs = job_filter.evaluate_jobs_list(company, scrape_result["data"])
            elif scrape_result["type"] == "raw_page":
                page_data = scrape_result["data"]
                extracted = job_filter.extract_jobs_from_raw_page(company, page_data["text"], page_data["links"])
                jobs = job_filter.evaluate_jobs_list(company, extracted)

            if jobs:
                caption = job_filter.format_jobs_caption(company, jobs)
                sheet.update_chosen_roles(worksheet, row, caption)
                matched_count += 1
            else:
                logger.info(f"No matching roles found for {company}.")
                sheet.update_chosen_roles(worksheet, row, "No matching roles found this week.")

        except Exception as e:
            logger.error(f"Error processing {company}: {e}", exc_info=True)
            try:
                sheet.update_chosen_roles(worksheet, row, f"Error: {str(e)}")
            except Exception:
                pass

    logger.info(f"Tab '{worksheet.title}' done. {matched_count}/{len(companies)} companies had matches.")


def run():
    logger.info("Starting AWS re/Start Job Tracker...")

    warnings = config.validate_config()
    for w in warnings:
        logger.warning(w)

    try:
        sheet = SheetHandler()
        worksheets = sheet.get_all_worksheets()
    except Exception as e:
        logger.error(f"Critical error accessing Google Sheets: {e}")
        sys.exit(1)

    logger.info(f"Found {len(worksheets)} tab(s): {[ws.title for ws in worksheets]}")

    for worksheet in worksheets:
        tab_name = worksheet.title.strip().lower()
        logger.info(f"--- Processing tab: '{worksheet.title}' ---")

        if any(kw in tab_name for kw in SKIP_TAB_KEYWORDS):
            logger.info(f"Skipping tab '{worksheet.title}'.")
            continue

        sheet.init_headers_if_empty(worksheet)
        process_hiring_partners_tab(sheet, worksheet)

    logger.info("All tabs processed. Run complete.")


if __name__ == "__main__":
    run()
