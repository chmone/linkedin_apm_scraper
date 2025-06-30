# This file will orchestrate the sequence of AI agents.
import time
import os
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

def run_workflow(jobs: list[Job], config) -> list[list[str]]:
    """
    Orchestrates the agent workflow.
    1. Validate jobs.
    2. Generate tailored resume and cover letter.
    3. Verify the generated content.
    
    Args:
        jobs: A list of Job objects scraped from LinkedIn.
        config: The application configuration object.
        
    Returns:
        A list of message groups. Each group is a list of strings, 
        where each string is a part of a notification to be sent.
    """
    
    print(f"Starting workflow for {len(jobs)} jobs.")
    final_message_groups = []
    sent_jobs = load_sent_jobs()

    for job in jobs:
        if job.url in sent_jobs:
            print(f"Skipping already processed job: {job.title}")
            continue
        try:
            print(f"--- Processing: {job.title} at {job.company} ---")

            is_fit = validation_agent.validate_job(job, config)
            if not is_fit:
                continue

            # Multi-attempt generation and review cycle
            rejection_reason = None
            for attempt in range(3):
                is_last_chance = (attempt == 2)
                print(f"Content generation attempt {attempt + 1}/3...")

                resume_suggestions, cover_letter = generation_agent.generate_content(
                    job, config, 
                    previous_rejection_reason=rejection_reason, 
                    is_last_chance=is_last_chance
                )

                if is_last_chance:
                    print("Final attempt, skipping review.")
                    is_good = True
                else:
                    is_good, reason = review_agent.review_content(job, resume_suggestions, cover_letter, config)
                    if not is_good:
                        rejection_reason = reason # Store reason for next attempt
                
                if is_good:
                    # Approved or final attempt
                    job_alert_message = f"""
                    **New Qualified Job Found!**

                    **Job Title:** {job.title}
                    **Company:** {job.company}
                    **Location:** {job.location}
                    **URL:** {job.search_url}
                    """
                    resume_suggestions_message = f"""
                    --- RESUME SUGGESTIONS ---
                    {resume_suggestions}
                    """
                    cover_letter_message = f"""
                    --- COVER LETTER DRAFT ---
                    {cover_letter}
                    """
                    final_message_groups.append([
                        job_alert_message, 
                        resume_suggestions_message, 
                        cover_letter_message
                    ])
                    save_sent_job(job.url)
                    break # Exit attempt loop on success
                else:
                    # Rejected, print to console and retry
                    print(f"Draft Rejected (Attempt {attempt + 1}/3): {job.title} at {job.company}")
                    print(f"Reason: {rejection_reason}")
                    print("*Will attempt to regenerate...*")
            
            print("Waiting 2 seconds before processing the next job...")
            time.sleep(2)

        except Exception as e:
            print(f"An error occurred processing job: {job.title} at {job.company}. Error: {e}")
            continue

    print("Workflow completed.")
    return final_message_groups