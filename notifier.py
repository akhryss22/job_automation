import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
import config

logger = logging.getLogger(__name__)

def chunk_message(text, limit=1900):
    """
    Chunks a long text into parts smaller than the limit (e.g. Discord 2000 char limit).
    """
    lines = text.split("\n")
    chunks = []
    current_chunk = []
    current_length = 0
    
    for line in lines:
        if current_length + len(line) + 1 > limit:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_length = len(line)
        else:
            current_chunk.append(line)
            current_length += len(line) + 1
            
    if current_chunk:
        chunks.append("\n".join(current_chunk))
        
    return chunks

def format_jobs_as_markdown(all_companies_jobs):
    """
    Formats the jobs data into markdown.
    """
    markdown_lines = ["# 🚀 Weekly Job Openings Update\n"]
    
    found_any = False
    for item in all_companies_jobs:
        company = item["company"]
        jobs = item["jobs"]
        if not jobs:
            continue
        
        found_any = True
        markdown_lines.append(f"### 🏢 {company}")
        for job in jobs:
            markdown_lines.append(f"- **[{job['title']}]({job['link']})**")
            markdown_lines.append(f"  *Reason: {job.get('reason', '')}*")
        markdown_lines.append("") # Spacer
        
    if not found_any:
        return "No new jobs matching the criteria were found this week."
        
    return "\n".join(markdown_lines)

def send_discord_notification(all_companies_jobs):
    """
    Sends the formatted job list to Discord using webhooks.
    Handles Discord's 2000 character limit by chunking.
    """
    if not config.DISCORD_WEBHOOK_URL:
        logger.warning("Discord webhook URL is not configured. Skipping Discord post.")
        return False

    markdown_text = format_jobs_as_markdown(all_companies_jobs)
    chunks = chunk_message(markdown_text)
    
    success = True
    for idx, chunk in enumerate(chunks):
        payload = {
            "content": chunk,
            "username": "AWS Re/Start Job Tracker",
            "avatar_url": "https://raw.githubusercontent.com/github/explore/80688e429a7d4ef2fca1e82350fe8e3517d3494d/topics/aws/aws.png"
        }
        
        try:
            logger.info(f"Sending message chunk {idx + 1}/{len(chunks)} to Discord...")
            response = requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            if response.status_code not in [200, 204]:
                logger.error(f"Failed to send to Discord. Status: {response.status_code}, Body: {response.text}")
                success = False
        except Exception as e:
            logger.error(f"Error sending Discord webhook: {e}")
            success = False
            
    return success

def send_email_notification(all_companies_jobs):
    """
    Sends an HTML email with the list of jobs.
    """
    if not config.SMTP_EMAIL or not config.SMTP_PASSWORD or not config.RECIPIENT_EMAILS:
        logger.warning("Email configurations are incomplete. Skipping email sending.")
        return False
        
    # Generate HTML content
    html_lines = [
        "<html><body style='font-family: Arial, sans-serif; color: #333; line-height: 1.6;'>",
        "<div style='max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;'>",
        "<h2 style='color: #FF9900; border-bottom: 2px solid #FF9900; padding-bottom: 10px;'>🚀 Weekly Job Openings Update</h2>",
        "<p>Hello, here are the selected junior-level and AWS-related roles matching your criteria for this week:</p>"
    ]
    
    found_any = False
    for item in all_companies_jobs:
        company = item["company"]
        jobs = item["jobs"]
        if not jobs:
            continue
        found_any = True
        
        html_lines.append(f"<div style='margin-bottom: 20px;'>")
        html_lines.append(f"<h3 style='margin: 0 0 10px 0; color: #111;'>🏢 {company}</h3>")
        html_lines.append("<ul style='padding-left: 20px; margin: 0;'>")
        for job in jobs:
            html_lines.append(
                f"<li style='margin-bottom: 8px;'>"
                f"<a href='{job['link']}' style='color: #0066cc; text-decoration: none; font-weight: bold;'>{job['title']}</a>"
                f"<div style='font-size: 13px; color: #666; font-style: italic;'>Why it matches: {job.get('reason', '')}</div>"
                f"</li>"
            )
        html_lines.append("</ul>")
        html_lines.append("</div>")
        
    if not found_any:
        html_lines.append("<p>No jobs matching the criteria were found for the monitored companies this week.</p>")
        
    html_lines.append("<hr style='border: 0; border-top: 1px solid #ddd; margin: 20px 0;'>")
    html_lines.append("<p style='font-size: 12px; color: #999;'>This is an automated report generated by the AWS Re/Start Job Tracker.</p>")
    html_lines.append("</div></body></html>")
    
    html_content = "".join(html_lines)
    
    # Setup SMTP connection and send email
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🚀 Weekly Job Openings Update"
        msg["From"] = config.SMTP_EMAIL
        msg["To"] = ", ".join(config.RECIPIENT_EMAILS)
        
        # Attach HTML body
        msg.attach(MIMEText(html_content, "html"))
        
        logger.info(f"Connecting to SMTP server {config.SMTP_SERVER}:{config.SMTP_PORT}...")
        server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
        server.starttls()
        server.login(config.SMTP_EMAIL, config.SMTP_PASSWORD)
        
        logger.info("Sending email notifications...")
        server.sendmail(config.SMTP_EMAIL, config.RECIPIENT_EMAILS, msg.as_string())
        server.quit()
        logger.info("Emails sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

def generate_facebook_caption(all_companies_jobs):
    """
    Generates a beautifully formatted text caption for manual Facebook posting.
    """
    caption_lines = [
        "🔥 WEEKLY JOB OPENINGS UPDATE 🔥\n",
        "Here are some great opportunities for fresh graduates, career shifters, and AWS re/Start grads. Check out the latest job openings below!\n"
    ]
    
    found_any = False
    for item in all_companies_jobs:
        company = item["company"]
        jobs = item["jobs"]
        if not jobs:
            continue
        found_any = True
        
        caption_lines.append(f"🏢 {company}")
        for job in jobs:
            caption_lines.append(f"✨ {job['title']}")
            caption_lines.append(f"🔗 Apply here: {job['link']}\n")
            
    if not found_any:
        return "No new jobs matching the criteria found this week."
        
    caption_lines.append("💻 Happy Job Hunting! Feel free to share this with anyone looking for a role. #AWS #CloudJobs #FreshGrads #EntryLevel")
    
    return "\n".join(caption_lines)
