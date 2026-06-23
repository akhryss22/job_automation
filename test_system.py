import logging
import sys
import os
from dotenv import load_dotenv

# Ensure the local path is in the search path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
import scraper
import job_filter
import notifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_system")

# Mock data
MOCK_LINKEDIN_JOBS = [
    {
        "title": "Junior AWS Cloud Associate",
        "link": "https://www.linkedin.com/jobs/view/mock123",
        "company": "eCloudvalley Philippines",
        "location": "Manila",
        "source": "Mock LinkedIn"
    },
    {
        "title": "Senior Cloud Solutions Architect (10+ years experience)",
        "link": "https://www.linkedin.com/jobs/view/mock456",
        "company": "eCloudvalley Philippines",
        "location": "Manila",
        "source": "Mock LinkedIn"
    },
    {
        "title": "Associate DevOps Specialist",
        "link": "https://www.linkedin.com/jobs/view/mock789",
        "company": "eCloudvalley Philippines",
        "location": "Manila",
        "source": "Mock LinkedIn"
    }
]

def run_dry_run_test():
    load_dotenv()
    logger.info("Starting Dry Run Verification...")
    
    # Check Gemini API Key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("No GEMINI_API_KEY found in environment or .env file.")
        logger.warning("Using mock evaluation fallback...")
        selected_jobs = [
            {
                "title": "Junior AWS Cloud Associate",
                "link": "https://www.linkedin.com/jobs/view/mock123",
                "reason": "AWS/cloud focused junior role matching the max 2 years criteria"
            }
        ]
    else:
        # Actually call Gemini with mock job list
        logger.info("Calling Gemini API to filter mock jobs list...")
        config.GEMINI_API_KEY = api_key
        
        selected_jobs = job_filter.evaluate_jobs_list("eCloudvalley Philippines", MOCK_LINKEDIN_JOBS)

    logger.info(f"Filtered {len(selected_jobs)} jobs matching the criteria:")
    for job in selected_jobs:
        logger.info(f" - {job['title']} ({job['link']})")
        logger.info(f"   Reason: {job.get('reason')}")

    # Format into cell caption
    caption = job_filter.format_jobs_caption("eCloudvalley Philippines", selected_jobs)
    logger.info("\n--- Formatted Sheet Caption ---\n" + caption + "\n----------------------------")

    # Generate Facebook post
    all_jobs_summary = [{
        "company": "eCloudvalley Philippines",
        "jobs": selected_jobs
    }]
    fb_post = notifier.generate_facebook_caption(all_jobs_summary)
    logger.info("\n--- Generated Facebook Post ---\n" + fb_post + "\n----------------------------")
    
    logger.info("Verification dry run completed successfully!")

if __name__ == "__main__":
    run_dry_run_test()
