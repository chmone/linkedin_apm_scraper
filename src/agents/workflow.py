# This file will orchestrate the sequence of AI agents.
import time
import os
import sys
from scraper.models import Job
from agents import validation_agent, generation_agent, review_agent

SENT_JOBS_FILE = "sent_jobs.log"

def load_sent_jobs():
    if not os.path.exists(SENT_JOBS_FILE):
        return set()
    with open(SENT_JOBS_FILE, "r") as f:
        return set(line.strip() for line in f)

def save_sent_job(job_url):
    with open(SENT_JOBS_FILE, "a") as f:
        f.write(job_url + "\\n")

def run_workflow(job: Job, config):
    """
    Runs the full AI workflow for a single job posting.
    """
    
    log_file = "sent_jobs.log"
    
    # Read the ideal job profile once for the workflow
    with open(config.ideal_job_profile, 'r') as f:
        ideal_job_profile_content = f.read()
    
    print(f"Starting workflow for job: {job.title}")

    # 1. Check if the job has already been sent
    if os.path.exists(log_file):
        sent_jobs = load_sent_jobs()
        if job.url in sent_jobs:
            print(f"Skipping already processed job: {job.title}")
            return []
    
    try:
        print(f"--- Processing: {job.title} at {job.company} ---")

        is_fit = validation_agent.validate_job(job, config)
        if not is_fit:
            return []

        # Multi-attempt generation and review cycle
        rejection_reason = None
        for attempt in range(3): # 3 attempts to generate and review
            print(f"Content generation attempt {attempt + 1}/3...")

            resume_suggestions, cover_letter = generation_agent.generate_content(
                job, config, ideal_job_profile_content,
                previous_rejection_reason=rejection_reason, 
                is_last_chance=(attempt==2)
            )

            if attempt == 2: # Last chance, accept it
                is_good = True
            else:
                is_good, reason = review_agent.review_content(
                    job, resume_suggestions, cover_letter, config, ideal_job_profile_content
                )
                if not is_good:
                    rejection_reason = reason # Store reason for next attempt
                else:
                    # Content is good, proceed to send
                    break
        
        if is_good:
            # Prepare the messages for the notifier
            job_alert_message = f"**New Job Alert: {job.title} at {job.company}**\n\n**Location:** {job.location}\n\n**URL:** {job.url}"
            resume_suggestions_message = f"**Resume Suggestions:**\n\n{resume_suggestions}"
            cover_letter_message = f"**Cover Letter:**\n\n{cover_letter}"

            final_message_groups = [[
                job_alert_message, 
                resume_suggestions_message, 
                cover_letter_message
            ]]
            save_sent_job(job.url)
            return final_message_groups
        else:
            print(f"Failed to generate acceptable content for {job.title} after 3 attempts.")

    except Exception as e:
        print(f"An error occurred processing job: {job.title} at {job.company}. Error: {e}", file=sys.stderr)
        return []

    print("Workflow completed.")
    return []