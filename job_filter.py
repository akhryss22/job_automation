import json
import logging
from google import genai
from google.genai import types
import config

logger = logging.getLogger(__name__)

# Use the recommended modern Gemini model
MODEL_NAME = "gemini-2.5-flash"

CRITERIA = """
1. Good for our AWS re/start program graduates (entry-level cloud, IT support, sysadmin, junior DevOps).
2. Fresh grads or people who didn't finish college (no strict 4-year degree requirements, or explicitly welcoming non-traditional backgrounds).
3. AWS/Cloud focus (uses AWS services, cloud administration, cloud support, or general cloud infrastructure).
4. Junior to mid level (maximum of 2 years experience required, entry-level, associate, or junior roles).
"""

def get_gemini_client():
    """Initializes and returns the GenAI Client."""
    # Pass api_key explicitly if set in config, otherwise it defaults to GEMINI_API_KEY env var
    if config.GEMINI_API_KEY:
        return genai.Client(api_key=config.GEMINI_API_KEY)
    return genai.Client()

def extract_jobs_from_raw_page(company_name, page_text, links):
    """
    Uses Gemini to extract job openings from a raw careers webpage.
    """
    if not config.GEMINI_API_KEY:
        logger.warning("Gemini API key is missing. Skipping raw page job extraction.")
        return []

    # Format links for the prompt
    formatted_links = "\n".join([f"- {l['text']}: {l['url']}" for l in links[:150]]) # Cap links list

    prompt = f"""
You are a job scraper assistant. Analyze the following webpage text and links from the careers portal of the company "{company_name}".
Extract all open job listings. For each job, identify its title and direct application/details URL.

Webpage Text:
{page_text[:8000]}

Webpage Links:
{formatted_links}

Respond ONLY with a JSON list of objects, each containing "title" and "link".
Example output:
[
  {{"title": "Junior Cloud Support Associate", "link": "https://company.com/careers/job1"}},
  {{"title": "IT Helpdesk Specialist", "link": "https://company.com/careers/job2"}}
]
"""
    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        jobs = json.loads(response.text)
        logger.info(f"Gemini extracted {len(jobs)} jobs from raw page for {company_name}")
        return jobs
    except Exception as e:
        logger.error(f"Error extracting jobs with Gemini for {company_name}: {e}")
        return []

def evaluate_jobs_list(company_name, jobs, max_results=8):
    """
    Evaluates a list of jobs against the criteria using Gemini.
    Filters and returns the selected jobs and formats them into a final caption.
    """
    if not config.GEMINI_API_KEY:
        logger.warning("Gemini API key is missing. Skipping job evaluation.")
        return []

    if not jobs:
        return []

    # Prepare jobs data for Gemini
    jobs_data = json.dumps(jobs, indent=2)

    prompt = f"""
You are a career placement officer matching candidates with job roles.
Your candidates are graduates of the AWS re/start program: junior-to-mid level cloud enthusiasts, fresh grads, and self-taught developers (max 2 years experience).

Evaluate the following list of jobs for the company "{company_name}" against these criteria:
{CRITERIA}

Jobs list:
{jobs_data}

Select a maximum of {max_results} jobs that are the best fit.
For each selected job, generate a concise one-line description explaining why it is a good fit.

Respond ONLY with a JSON list of objects, each containing:
- "title": Job title
- "link": Job URL
- "reason": A very brief 1-sentence reason why it fits (e.g. "Entry-level AWS role with 1 year experience requirement").

Example response:
[
  {{
    "title": "Cloud Support Associate",
    "link": "https://linkedin.com/jobs/view/123",
    "reason": "Junior AWS support role requiring 0-2 years experience"
  }}
]
"""
    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        selected_jobs = json.loads(response.text)
        logger.info(f"Gemini matched {len(selected_jobs)} jobs for {company_name} against criteria.")
        return selected_jobs
    except Exception as e:
        logger.error(f"Error evaluating jobs with Gemini for {company_name}: {e}")
        return []

def format_jobs_caption(company_name, selected_jobs):
    """
    Formats the selected jobs into the exact format requested:
    "Company Name
    Role (embedded with the link to the linkedin job post/portal/page post)"
    
    Using standard markdown link formatting for the spreadsheet cell.
    """
    if not selected_jobs:
        return ""
    
    caption_lines = [f"{company_name}"]
    for job in selected_jobs:
        title = job.get("title")
        link = job.get("link")
        # Format as: - [Role Title](Link)
        caption_lines.append(f"- [{title}]({link})")
        
    return "\n".join(caption_lines)
