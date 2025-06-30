# This file will contain the Content Review Agent.
# This agent will take the generated content and review it
# for quality, tone, and accuracy. It can send it back to the
# generation agent if it needs improvement.
from openai import OpenAI
from scraper.models import Job

def review_content(job: Job, resume_suggestions: str, cover_letter: str, config) -> tuple[bool, str]:
    """
    Reviews the generated content to ensure it's high quality and relevant.
    """
    print(f"Reviewing content for: {job.title}...")

    with open(config.ideal_job_profile, 'r') as f:
        ideal_job_profile_content = f.read()

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=config.openrouter_api_key,
    )
    
    prompt = f"""
    You are a meticulous hiring manager with high standards. Your task is to review an AI-generated cover letter and resume suggestions for a candidate.

    **Candidate's Ideal Job Profile:**
    ---
    {ideal_job_profile_content}
    ---

    **Original Job Posting:**
    ---
    **Title:** {job.title}
    **Company:** {job.company}
    **Description:**
    {job.description}
    ---

    **The AI-Generated Content to Review:**
    ---
    **Resume Suggestions:**
    {resume_suggestions}

    **Cover Letter:**
    {cover_letter}
    ---

    **Your Task:**
    Review the job, resume suggestions, and cover letter. 
    1.  First, decide if the generated content is high-quality, professional, and tailored to the job. 
    2.  Then, on the first line of your response, write **only** "YES" or "NO".
    3.  On the second line, provide a brief, one-sentence reason for your decision.

    Please format your response with a clear separator between the two parts, like this:
    
    YES
    ---SPLIT---
    The cover letter effectively connects the candidate's experience to the job requirements.
    """

    try:
        response = client.chat.completions.create(
            model="google/gemini-pro-1.5",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = response.choices[0].message.content
        parts = response_text.split("---SPLIT---")
        if len(parts) == 2:
            decision = parts[0].strip().upper()
            reason = parts[1].strip()
            print(f"Review decision: {decision}. Reason: {reason}")
            return decision == "YES", reason
        else:
            print("Warning: AI review response did not contain the expected '---SPLIT---' separator.")
            # Fallback for old format
            is_yes = "YES" in response_text.upper()
            reason = "Could not parse review response." if not is_yes else "Approved under fallback."
            return is_yes, reason

    except Exception as e:
        print(f"An error occurred during AI review: {e}")
        raise e

    # This part should not be reached if an exception occurs
    return False, "Approved under fallback."