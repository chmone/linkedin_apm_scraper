# This file will contain the Job Validation Agent.
# This agent will take a Job object and the ideal_job_profile.txt
# and determine if the job is a good fit.
from openai import OpenAI
from scraper.models import Job

def validate_job(job: Job, config) -> bool:
    """
    Uses an LLM to validate if a job posting is a good fit based on the ideal job profile.
    """
    print(f"Validating job: {job.title}...")

    with open(config.ideal_job_profile, 'r') as f:
        ideal_job_profile_content = f.read()

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=config.openrouter_api_key,
    )

    prompt = f"""
    You are a strict job validation agent. Your task is to determine if a job posting is a good fit for a candidate based on their ideal job profile.

    **Ideal Job Profile:**
    ---
    {ideal_job_profile_content}
    ---

    **Job Posting Details:**
    ---
    **Title:** {job.title}
    **Company:** {job.company}
    **Description:**
    {job.description}
    ---
    
    **CRITICAL INSTRUCTIONS:**
    1.  **Adhere Strictly to Exclusions:** You MUST reject any job that contains senior-level titles like "Senior," "Lead," "Group," "Director," or "Head" in the job title. The candidate is NOT looking for senior roles.
    2.  **Verify Experience Level:** Scrutinize the description for the required years of experience. If the job requires more than 5 years of product management experience, you MUST reject it.
    3.  **No Exceptions:** Do not make exceptions, even if some keywords match. The role's seniority and experience requirements are the most important criteria. A "Lead" role is NOT a fit, regardless of other details.

    Based on these strict rules, is this job a good fit? Answer with only "YES" or "NO".
    """

    try:
        response = client.chat.completions.create(
            model="google/gemini-pro",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        answer = response.choices[0].message.content.strip().upper()
        print(f"Model validation result: {answer}")
        
        return "YES" in answer
        
    except Exception as e:
        print(f"An error occurred during AI validation: {e}")
        # Re-raise the exception to be caught by the main workflow
        raise e

    # This part should not be reached if an exception occurs
    return False