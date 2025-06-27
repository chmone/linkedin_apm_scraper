# This file will orchestrate the sequence of AI agents.
import time
from scraper.models import Job
from agents import validation_agent, generation_agent, review_agent
from google.api_core import exceptions as google_exceptions

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

    for job in jobs:
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
                    message_part_1 = f"""
                    **New Qualified Job Found!** (Attempt: {attempt + 1}/3)
                    **Job Title:** {job.title}
                    **Company:** {job.company}
                    **Location:** {job.location}
                    **URL:** {job.url}
                    --- RESUME SUGGESTIONS ---
                    {resume_suggestions}
                    """
                    message_part_2 = f"""
                    --- COVER LETTER DRAFT ---
                    {cover_letter}
                    """
                    final_message_groups.append([message_part_1, message_part_2])
                    break # Exit attempt loop on success
                else:
                    # Rejected, print to console and retry
                    print(f"Draft Rejected (Attempt {attempt + 1}/3): {job.title} at {job.company}")
                    print(f"Reason: {rejection_reason}")
                    print("*Will attempt to regenerate...*")
            
            print("Waiting 20 seconds before processing the next job...")
            time.sleep(20)

        except google_exceptions.ResourceExhausted as e:
            print(f"Google AI API quota exceeded. Stopping workflow. Error: {e}")
            break
        except Exception as e:
            print(f"An unexpected error occurred processing job {job.title}: {e}")
            continue

    print("Workflow completed.")
    return final_message_groups