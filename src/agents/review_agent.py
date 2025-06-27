# This file will contain the Content Review Agent.
# This agent will take the generated content and review it
# for quality, tone, and accuracy. It can send it back to the
# generation agent if it needs improvement.
from openai import OpenAI
from scraper.models import Job

def review_content(job: Job, resume_suggestions: str, cover_letter: str, config) -> tuple:
    """
    Reviews the generated content for quality and accuracy using a generative AI model.
    
    Args:
        job: The Job object.
        resume_suggestions: The generated resume suggestions.
        cover_letter: The generated cover letter.
        config: The application configuration object.
        
    Returns:
        A tuple containing a boolean decision and a reason string.
    """
    if not config.openrouter_api_key:
        print("Skipping review: OPENROUTER_API_KEY not configured.")
        # Default to True to not block the pipeline if the key is missing
        return True, "Approved under fallback."

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=config.openrouter_api_key,
    )

    prompt = f"""
    You are a professional editor and career coach. Your task is to review AI-generated content for a job application to ensure it is high quality.

    **The Job:**
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
        print(f"Reviewing content for: {job.title}...")
        response = client.chat.completions.create(
            model="google/gemini-pro-2.5",
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