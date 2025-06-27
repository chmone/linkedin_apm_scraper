# This file will contain the Job Validation Agent.
# This agent will take a Job object and the ideal_job_profile.txt
# and determine if the job is a good fit.
import google.generativeai as genai
from scraper.models import Job

def validate_job(job: Job, config) -> bool:
    """
    Validates if a job is a good fit by using a generative AI model.
    
    Args:
        job: A Job object.
        config: The application configuration object.
        
    Returns:
        True if the job is a good fit, False otherwise.
    """
    if not config.google_api_key:
        print("Skipping validation: GOOGLE_API_KEY not configured.")
        return False

    genai.configure(api_key=config.google_api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = f"""
    Based on the following ideal job profile and the provided job description, please determine if this job is a good fit.
    Answer with only 'YES' or 'NO'.

    --- IDEAL JOB PROFILE ---
    {config.ideal_job_profile}

    --- JOB DESCRIPTION ---
    **Title:** {job.title}
    **Company:** {job.company}
    **Description:**
    {job.description}
    """

    try:
        print(f"Validating job: {job.title}...")
        response = model.generate_content(prompt)
        answer = response.text.strip().upper()
        print(f"Model validation result: {answer}")
        
        return "YES" in answer
        
    except Exception as e:
        print(f"An error occurred during AI validation: {e}")
        # Re-raise the exception to be caught by the main workflow
        raise e

    # This part should not be reached if an exception occurs
    return False