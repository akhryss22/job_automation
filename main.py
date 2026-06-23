import logging
import sys
import config
from sheet_handler import SheetHandler
import scraper
import job_filter
import notifier

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("job_tracker")

def run():
    logger.info("Starting AWS Re/Start Job Tracker Automation...")
    
    # 1. Validate Configuration
    warnings = config.validate_config()
    if warnings:
        for warning in warnings:
            logger.warning(warning)
            
    # 2. Connect to Google Sheets
    try:
        sheet = SheetHandler()
        sheet.init_headers_if_empty()
        companies = sheet.get_companies_to_scrape()
    except Exception as e:
        logger.error(f"Critical error accessing Google Sheets: {e}")
        logger.error("Exiting automation run.")
        sys.exit(1)
        
    if not companies:
        logger.info("No companies found in the spreadsheet to scrape. Add companies to Column A and URLs to Column B.")
        return

    logger.info(f"Loaded {len(companies)} companies to monitor.")
    all_selected_jobs = []

    # 3. Process each company
    for item in companies:
        row = item["row"]
        company = item["company"]
        url = item["url"]
        
        logger.info(f"Processing row {row}: {company} ({url})")
        
        try:
            # Scrape jobs/content
            scrape_result = scraper.get_jobs_for_company(company, url)
            
            jobs = []
            if scrape_result["type"] == "jobs_list":
                raw_jobs = scrape_result["data"]
                # Evaluate the raw jobs
                jobs = job_filter.evaluate_jobs_list(company, raw_jobs)
            elif scrape_result["type"] == "raw_page":
                page_data = scrape_result["data"]
                # Extract jobs from raw HTML page using Gemini
                extracted_jobs = job_filter.extract_jobs_from_raw_page(company, page_data["text"], page_data["links"])
                # Evaluate the extracted jobs
                jobs = job_filter.evaluate_jobs_list(company, extracted_jobs)
                
            # If jobs matched criteria, update Sheet and save for notifications
            if jobs:
                # Format roles into spreadsheet cell format
                sheet_caption = job_filter.format_jobs_caption(company, jobs)
                # Write to Column C
                sheet.update_chosen_roles(row, sheet_caption)
                
                # Accumulate for global notifications
                all_selected_jobs.append({
                    "company": company,
                    "jobs": jobs
                })
            else:
                logger.info(f"No matching roles found for {company} this week.")
                # Optional: Clear the cell to show it was checked and empty
                sheet.update_chosen_roles(row, "No matching roles found this week.")
                
        except Exception as e:
            logger.error(f"Error processing {company}: {e}", exc_info=True)
            # Write error indicator to sheet so the user knows
            try:
                sheet.update_chosen_roles(row, f"Error checking jobs: {str(e)}")
            except Exception as se:
                logger.error(f"Failed to write error to sheet: {se}")

    # 4. Final log summary
    if all_selected_jobs:
        logger.info(f"Completed run. Wrote matches to Google Sheet for {len(all_selected_jobs)} companies.")
    else:
        logger.info("Completed run. No matching job openings found for any company this week.")

if __name__ == "__main__":
    run()
