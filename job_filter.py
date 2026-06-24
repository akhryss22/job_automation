import json
import logging
from google import genai
from google.genai import types
import config

logger = logging.getLogger(__name__)

# Use the recommended modern Gemini model
MODEL_NAME = "gemini-2.5-flash"

CRITERIA = """
CANDIDATE PROFILE:
Graduates of the AWS re/Start programme — a rigorous, hands-on cloud training program.
They are diverse: career switchers, upskillers, people from non-IT backgrounds who have retrained.
Most are AWS Certified Cloud Practitioners or well-prepared to be.
They have practical lab experience but may have limited formal IT work history (0-2 years max).

FILTERING RULES (all must pass):
1. LOCATION: The role must be based in Metro Manila, Philippines OR be fully Remote work open to Philippines-based applicants.
   - REJECT any role that is overseas, onsite abroad, or does not mention Philippines / Metro Manila / remote PH.
   - If location is unclear or not mentioned, lean toward REJECTION.
2. EXPERIENCE: Junior to mid-level only. Maximum 2 years of experience required.
   - Reject roles that require 3+ years of experience.
3. EDUCATION: No strict 4-year CS/IT degree requirement. Roles that welcome bootcamp graduates, non-traditional backgrounds, or equivalent experience are preferred.
4. ROLE TYPE: Cloud, AWS, IT support, sysadmin, DevOps, and junior tech roles are ideal.
   However, also accept transferable roles where our alumni's skills apply — e.g. technical consulting, IT sales/pre-sales, tech support, business analyst (tech-focused), project coordination (IT), etc.
   Use good judgment: if an AWS-certified career switcher could credibly apply, include it.
5. DATE: Posted within the last 5 days. Discard older postings.
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
You are a career placement officer for AWS re/Start programme alumni in the Philippines.

Alumni profile: AWS Certified Cloud Practitioners (or near-certified), career switchers and upskillers from diverse backgrounds, hands-on practical training, 0-2 years formal IT work experience.

Evaluate this list of jobs from "{company_name}" and apply the following criteria strictly:
{CRITERIA}

Jobs list:
{jobs_data}

IMPORTANT: REJECT any job that is not in Metro Manila or remote-open to Philippines. Do not include overseas roles.

Select a maximum of {max_results} jobs that pass ALL criteria above.
For each selected job, provide a brief reason why it fits our alumni.

Respond ONLY with a JSON list. If NO jobs pass all criteria, return an empty list [].
Each object must contain:
- "title": Job title
- "link": Job URL  
- "reason": 1-sentence reason why it fits (mention location + experience level)

Example:
[
  {{
    "title": "Cloud Support Associate",
    "link": "https://linkedin.com/jobs/view/123",
    "reason": "Metro Manila-based, entry-level AWS role requiring 0-1 year experience."
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
