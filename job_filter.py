import json
import logging
import time
import config

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

CRITERIA = """
=== AWS re/Start ALUMNI PROFILE ===
Graduates of the AWS re/Start programme — an intensive, hands-on cloud training initiative
by Amazon Web Services. Alumni are career switchers, fresh graduates, and upskillers from
diverse (often non-IT) backgrounds who retrained into tech. They have:
  - AWS Certified Cloud Practitioner certification (or actively preparing for it)
  - Hands-on lab experience: EC2, S3, IAM, VPC, RDS, Lambda, CloudFormation, CLI
  - Linux command line basics, networking fundamentals, security concepts
  - Python/Bash scripting exposure
  - Real-world problem-solving labs and capstone projects
  - 0 to 2 years of formal IT work experience (may have years of other work experience)
  - Strong adaptability, motivated career changers — many come from customer service,
    admin, BPO, teaching, sales, and other backgrounds

=== FILTERING RULES (ALL must pass) ===

── RULE 1: LOCATION ─────────────────────────────────────────────────────────
Accept roles located in:
  - Metro Manila / NCR and surrounding areas (Rizal, Bulacan, Cavite, Laguna, Pampanga)
  - Cebu City and broader Visayas region
  - Northern Luzon: Baguio, Clark, Pampanga, La Union, Dagupan
  - Fully remote work that explicitly accepts Philippines-based applicants

REJECT if:
  - Role is based overseas (Singapore, USA, UAE, Australia, etc.)
  - Role requires physical relocation outside the Philippines
  - No Philippines mention AND no remote option (lean toward reject if ambiguous)

Note: If location info is absent from the job data, do NOT auto-reject —
the jobs in this list are pre-scraped from Philippines sources. Only reject
on location if the job explicitly states an overseas base.

── RULE 2: EXPERIENCE LEVEL ─────────────────────────────────────────────────
Accept:
  - Entry-level, Junior, Associate, Graduate trainee, Fresh graduate
  - 0 to 2 years of experience required
  - Roles that say "no experience required" or "experience is a plus (not required)"
  - Roles that welcome career shifters, non-traditional backgrounds, or bootcamp grads

REJECT:
  - Roles explicitly requiring 3+ years of experience
  - Senior, Lead, Principal, Manager, Director, VP level roles
  - Roles requiring 5+ years, extensive/deep expertise, or expert-level certifications

── RULE 3: EDUCATION ────────────────────────────────────────────────────────
Accept:
  - No degree requirement, or "Bachelor's degree preferred but not required"
  - Roles open to equivalent work experience, certifications, or training
  - Roles that list AWS Cloud Practitioner or similar certs as a qualification

REJECT:
  - Roles with a strict mandatory 4-year CS/IT/Engineering degree
    (UNLESS the role is otherwise clearly suitable and the degree is just a formality)

── RULE 4: ROLE TYPE — DIRECT CLOUD & IT ROLES ──────────────────────────────
These are ideal matches — accept freely if entry-level and PH-based:

  Cloud & Infrastructure:
    Cloud Support Associate, Cloud Engineer (Junior), Cloud Administrator,
    Cloud Operations Associate, AWS Support Engineer, Cloud Infrastructure Associate,
    Junior DevOps Engineer, DevOps Associate, Platform Engineer (Associate),
    Site Reliability Engineer (Entry), Systems Administrator (Junior),
    Infrastructure Associate, Linux Administrator (Junior),
    Network Administrator (Junior), Network Support Engineer,
    NOC Engineer, NOC Analyst, Network Operations Center Staff

  IT Support & Service Desk:
    IT Support Analyst, IT Help Desk (L1/L2), IT Support Specialist,
    Technical Support Engineer, Service Desk Analyst, Desktop Support Engineer,
    IT Operations Staff, Application Support Analyst,
    Systems Support Engineer, End-User Computing Analyst

  Security & Compliance (Entry):
    IT Security Analyst (Junior), Cybersecurity Associate,
    GRC Analyst (Entry), Information Security Associate,
    SOC Analyst (Tier 1), Vulnerability Assessment Associate

  Data & Monitoring (Entry):
    Data Operations Associate, IT Monitoring Analyst, Data Center Operations

── RULE 5: ROLE TYPE — TRANSFERABLE ROLES ───────────────────────────────────
Accept these roles where AWS re/Start skills are genuinely applicable.
Use judgment: would an AWS-certified career switcher with cloud fundamentals
and strong soft skills credibly apply for this?

  Consulting & Advisory:
    Technical Consultant (Associate/Junior), IT Consultant (Entry),
    Solutions Consultant, Implementation Consultant,
    Cloud Solutions Associate, Digital Transformation Associate,
    IT Advisory Associate, Managed Services Consultant (Junior)

  Pre-Sales & Sales Engineering:
    Pre-Sales Engineer (Associate), Solutions Engineer (Junior),
    Technical Sales Associate, IT Sales Engineer,
    Cloud Sales Associate, Inside Sales Engineer (Tech)

  Project & Operations:
    IT Project Coordinator, IT Project Associate,
    Delivery Analyst, Service Delivery Associate,
    IT Operations Coordinator, Technology Associate,
    IT Procurement Associate, Vendor Management Associate (IT)

  Customer-Facing Tech Roles:
    Technical Account Associate, Customer Success Associate (Tech/SaaS),
    Customer Implementation Specialist, Technical Customer Support,
    Client Success Engineer (Entry), Onboarding Specialist (Tech)

  Analysis & Reporting:
    Business Analyst (IT/Tech-focused), IT Analyst, Process Analyst (Tech),
    Data Analyst (Entry, with IT/tech tools focus), Systems Analyst (Junior),
    IT Risk Analyst (Entry), IT Audit Associate

  Training & Enablement:
    Technical Trainer (Associate), IT Trainer, Cloud Trainer,
    Technology Enablement Associate

  Others with clear IT/tech component:
    Technical Writer (IT), IT Documentation Specialist,
    Quality Analyst (IT/tech process), ITSM Analyst (Entry)

REJECT these regardless of how they are titled:
  - Pure finance roles (Accountant, Bookkeeper, Treasury) with no IT component
  - Pure HR roles (HR Associate, Recruiter) unless it is specifically HRIS/IT
  - Non-tech sales (Real estate, Insurance, FMCG, direct selling)
  - Purely managerial or executive roles with no hands-on technical element
  - Roles requiring deep domain expertise unrelated to IT (e.g., physician, lawyer, engineer PE)
  - MLM, networking, commission-only recruitment roles disguised as "IT jobs"

── RULE 6: HIRING INTENT ────────────────────────────────────────────────────
Prefer:
  - Specific, detailed job description (not a generic "we are always hiring" page)
  - Recently posted (within the last 5 days)
  - Clear company name and legitimate employer identity
  - Roles with defined responsibilities and qualifications

REJECT:
  - Vague evergreen postings ("Various IT roles — apply anytime")
  - Postings with no company name or suspicious company identity
  - Roles posted by unknown entities with no online presence

── RULE 7: CREDIBILITY & FRAUD CHECK ────────────────────────────────────────
REJECT if any of these red flags appear:
  - Unrealistic pay promises ("earn 80k/day", "no experience needed, high salary")
  - Upfront fees, investments, or capital required from the applicant
  - Commission-only compensation for a tech role with no base salary
  - MLM / pyramid / referral chain structure described in the role
  - Overly vague responsibilities ("marketing", "operations", "growth") with no tech detail
  - Suspicious company with no verifiable identity
"""


# ── Groq (primary) ────────────────────────────────────────
def call_groq(prompt):
    """Calls Groq API (llama-3.1-8b-instant — 500k tokens/day). Returns parsed JSON or raises."""
    from groq import Groq
    client = Groq(api_key=config.GROQ_API_KEY)
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
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
    """Calls Gemini as fallback. Returns parsed JSON list or raises."""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash-latest",
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

import urllib.parse

def normalize_url(url):
    """Normalizes a URL for comparison."""
    if not url:
        return ""
    url = url.strip()
    if url.endswith('/'):
        url = url[:-1]
    try:
        parsed = urllib.parse.urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path
        return f"{scheme}://{netloc}{path}"
    except Exception:
        return url.lower()


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

CRITICAL INSTRUCTIONS:
- You must ONLY extract jobs that are actually listed in the Webpage Text below.
- The "link" for each job MUST be chosen from the Webpage Links list below.
- Do NOT extract navigation links or generic URLs (like the main Careers page, Contact Us, About Us, Privacy Policy, Login, Sign Up, or Social Media URLs). The "link" MUST be a direct link to the specific job description.
- Do NOT hallucinate or invent any jobs.
- Do NOT invent or make up any URLs.
- If no jobs are listed, return an empty array [].

Webpage Text:
{page_text[:8000]}

Webpage Links:
{formatted_links}

Return a JSON array of objects with "title" and "link" fields only.
Example: [{{"title": "Cloud Support Associate", "link": "https://company.com/jobs/1"}}]
"""
    jobs = call_ai(prompt, context=f"— extract for {company_name}")
    
    # Python-side validation: ensure links match the input links list
    valid_urls_norm = {normalize_url(l["url"]): l["url"] for l in links if l.get("url")}
    
    valid_extracted = []
    for job in jobs:
        title = job.get("title", "").strip()
        link = job.get("link", "").strip()
        if title and link:
            norm_link = normalize_url(link)
            if norm_link in valid_urls_norm:
                valid_extracted.append({
                    "title": title,
                    "link": valid_urls_norm[norm_link]
                })
            else:
                logger.warning(f"Discarding hallucinated link in extraction for {company_name}: {link}")
                
    logger.info(f"AI extracted {len(valid_extracted)} validated jobs from raw page for {company_name}")
    return valid_extracted


def evaluate_jobs_list(company_name, jobs, max_results=8):
    """Filters a list of jobs against our criteria using AI. Returns matching jobs."""
    if not config.GROQ_API_KEY and not config.GEMINI_API_KEY:
        logger.warning("No AI API key configured. Skipping evaluation.")
        return []

    if not jobs:
        return []

    jobs_data = json.dumps(jobs, indent=2)

    prompt = f"""
You are a job filter for AWS re/Start programme alumni in the Philippines.

CRITICAL INSTRUCTIONS:
- You must ONLY select jobs from the "Jobs" list provided below.
- Do NOT generate, invent, or modify any job titles or URLs.
- The output URLs must match the input URLs EXACTLY.
- If none of the provided jobs qualify, you MUST return an empty list `[]`.

Filter this list of jobs from "{company_name}" using these criteria:
{CRITERIA}

CREDIBILITY CHECK — also reject postings that show ANY of these red flags:
- No company name or vague company identity
- Unrealistic pay promises ("earn 50k/day", "no experience, earn big")
- Upfront payment or investment required
- Purely commission-only with no base salary for a tech role
- MLM / networking / recruitment chain patterns
- Extremely vague job description with no real responsibilities listed

Jobs:
{jobs_data}

Return a JSON array of up to {max_results} jobs that pass ALL criteria AND credibility check.
Return [] if none qualify.

Each item must have ONLY:
- "title": job title
- "link": job URL
"""
    selected = call_ai(prompt, context=f"— evaluate for {company_name}")
    
    # Python-side validation: ensure links match the input list
    input_jobs_by_norm_link = {normalize_url(j.get("link")): j for j in jobs if j.get("link")}
    
    valid_selected = []
    for s_job in selected:
        s_link = s_job.get("link", "").strip()
        if s_link:
            norm_link = normalize_url(s_link)
            if norm_link in input_jobs_by_norm_link:
                orig_job = input_jobs_by_norm_link[norm_link]
                valid_selected.append({
                    "title": s_job.get("title", "").strip() or orig_job.get("title"),
                    "link": orig_job.get("link")
                })
            else:
                logger.warning(f"Discarding hallucinated link in evaluation for {company_name}: {s_link}")
                
    logger.info(f"AI matched {len(valid_selected)} validated jobs for {company_name}")
    return valid_selected


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
