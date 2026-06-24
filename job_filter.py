import json
import logging
import time
import config

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

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


# ── Groq (primary) ────────────────────────────────────────
def call_groq(prompt):
    """Calls Groq API (llama-3.3-70b). Returns parsed JSON or raises."""
    from groq import Groq
    client = Groq(api_key=config.GROQ_API_KEY)
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            text = response.choices[0].message.content
            # Groq with json_object mode returns a single JSON object; wrap if needed
            parsed = json.loads(text)
            # Normalize: our prompts expect a list; Groq may return {"jobs": [...]}
            if isinstance(parsed, list):
                return parsed
            for key in parsed:
                if isinstance(parsed[key], list):
                    return parsed[key]
            return []
        except Exception as e:
            err = str(e)
            if ("429" in err or "rate_limit" in err.lower()) and attempt < MAX_RETRIES - 1:
                wait = 15 * (attempt + 1)
                logger.warning(f"Groq rate limited. Retrying in {wait}s... ({attempt+1}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                raise


# ── Gemini (fallback) ──────────────────────────────────────
def call_gemini(prompt):
    """Calls Gemini 1.5-flash as fallback. Returns parsed JSON list or raises."""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return json.loads(response.text)
        except Exception as e:
            err = str(e)
            if "429" in err and attempt < MAX_RETRIES - 1:
                wait = 15 * (attempt + 1)
                logger.warning(f"Gemini rate limited. Retrying in {wait}s... ({attempt+1}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                raise


def call_ai(prompt, context=""):
    """
    Calls Groq first; falls back to Gemini if Groq fails.
    Returns a parsed Python list.
    """
    if config.GROQ_API_KEY:
        try:
            result = call_groq(prompt)
            logger.info(f"Groq OK {context}")
            return result
        except Exception as e:
            logger.warning(f"Groq failed ({e}). Falling back to Gemini...")

    if config.GEMINI_API_KEY:
        try:
            result = call_gemini(prompt)
            logger.info(f"Gemini fallback OK {context}")
            return result
        except Exception as e:
            logger.error(f"Gemini also failed ({e}).")

    logger.error("No AI provider available.")
    return []


# ── Public functions ───────────────────────────────────────

def extract_jobs_from_raw_page(company_name, page_text, links):
    """Uses AI to extract job listings from a raw careers webpage."""
    if not config.GROQ_API_KEY and not config.GEMINI_API_KEY:
        logger.warning("No AI API key configured. Skipping extraction.")
        return []

    formatted_links = "\n".join([f"- {l['text']}: {l['url']}" for l in links[:150]])

    prompt = f"""
You are a job scraper. Extract all open job listings from this careers page for "{company_name}".

Webpage Text:
{page_text[:8000]}

Webpage Links:
{formatted_links}

Return a JSON array of objects with "title" and "link" fields only.
If no jobs found, return an empty array [].
Example: [{{"title": "Cloud Support Associate", "link": "https://company.com/jobs/1"}}]
"""
    jobs = call_ai(prompt, context=f"— extract for {company_name}")
    logger.info(f"AI extracted {len(jobs)} jobs from raw page for {company_name}")
    return jobs


def evaluate_jobs_list(company_name, jobs, max_results=8):
    """Filters a list of jobs against our criteria using AI. Returns matching jobs."""
    if not config.GROQ_API_KEY and not config.GEMINI_API_KEY:
        logger.warning("No AI API key configured. Skipping evaluation.")
        return []

    if not jobs:
        return []

    jobs_data = json.dumps(jobs, indent=2)

    prompt = f"""
You are a career placement officer for AWS re/Start programme alumni in the Philippines.

Alumni profile: AWS Certified Cloud Practitioners (or near-certified), career switchers from diverse backgrounds, 0-2 years formal IT work experience.

Evaluate this list of jobs from "{company_name}" strictly against these criteria:
{CRITERIA}

Jobs list:
{jobs_data}

IMPORTANT: REJECT any job that is not in Metro Manila or remote-open to Philippines. Overseas roles must be excluded.

Select up to {max_results} jobs that pass ALL criteria. Return [] if none qualify.

Return a JSON array. Each item must have:
- "title": job title
- "link": job URL
- "reason": 1-sentence reason (mention location + seniority level)

Example:
[{{"title": "Cloud Support Associate", "link": "https://linkedin.com/jobs/view/123", "reason": "Metro Manila-based entry-level AWS role, 0-1 year experience required."}}]
"""
    selected = call_ai(prompt, context=f"— evaluate for {company_name}")
    logger.info(f"AI matched {len(selected)} jobs for {company_name}")
    return selected


def format_jobs_caption(company_name, selected_jobs):
    """Formats selected jobs as a plain text caption for the Google Sheet cell."""
    if not selected_jobs:
        return ""
    lines = [company_name]
    for job in selected_jobs:
        title = job.get("title", "")
        link = job.get("link", "")
        lines.append(f"- [{title}]({link})")
    return "\n".join(lines)
