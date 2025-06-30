# This file will contain the Content Generation Agent.
# This agent will take a qualified Job object and generate
# tailored resume bullet points and a cover letter.
import json
from openai import OpenAI
from scraper.models import Job

def generate_content(job: Job, config, previous_rejection_reason: str = None, is_last_chance: bool = False) -> tuple[str, str]:
    """
    Generates tailored resume bullet points and a cover letter using a generative AI model.
    
    Args:
        job: A validated Job object.
        config: The application configuration object.
        previous_rejection_reason: The reason for the previous rejection, if any.
        is_last_chance: Whether this is the final attempt.
        
    Returns:
        A tuple containing the resume suggestions and the cover letter.
    """
    if not config.openrouter_api_key:
        print("Skipping content generation: OPENROUTER_API_KEY not configured.")
        return "Content generation skipped due to missing API key.", "Content generation skipped."

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=config.openrouter_api_key,
    )

    print(f"Generating content for: {job.title}...")
    
    with open(config.ideal_job_profile, 'r') as f:
        ideal_job_profile_content = f.read()

    with open(config.resume, 'r') as f:
        resume_content = f.read()

    # Prepare the prompts
    resume_json = json.dumps(config.resume_data, indent=2)
    writing_samples = "\n---\n".join(config.writing_style_samples.values())
    
    # Add dynamic prompts for retry logic
    retry_prompt = ""
    if previous_rejection_reason:
        retry_prompt += f"\\n**Feedback from Previous Attempt:**\\nThe previous version was rejected for the following reason: '{previous_rejection_reason}'. Please address this feedback carefully in your new draft.\\n"
    
    if is_last_chance:
        retry_prompt += "\\n**This is your final attempt.** Please generate the highest quality content possible, as this will be sent directly to the user without further review.\\n"

    prompt = f"""
    You are an expert career coach and resume writer. Your task is to help a candidate tailor their resume and write a compelling cover letter for a specific job posting.

    **Candidate's Resume:**
    ---
    {resume_content}
    ---

    **Candidate's Ideal Job Profile:**
    ---
    {ideal_job_profile_content}
    ---
    
    **Candidate's Writing Style (emulate this):**
    ---
    {writing_samples}
    ---

    **The Job:**
    ---
    **Title:** {job.title}
    **Company:** {job.company}
    **Description:**
    {job.description}
    ---

    {retry_prompt}

    **Your Task:**
    Based on all the information provided, generate two pieces of content:
    1.  **Resume Suggestions:** Provide 3-5 specific, actionable bullet points on how to tailor the resume to this job.
    2.  **Cover Letter:** Write a compelling and professional cover letter (2-3 paragraphs).

    Please format your response with a clear separator between the two parts, like this:
    
    [Resume Suggestions]
    ---SPLIT---
    [Cover Letter]
    """

    try:
        response = client.chat.completions.create(
            model="google/gemini-2.5-pro",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = response.choices[0].message.content
        parts = response_text.split("---SPLIT---")
        if len(parts) == 2:
            resume_suggestions = parts[0].strip()
            cover_letter = parts[1].strip()
            print("Successfully generated content.")
            return resume_suggestions, cover_letter
        else:
            print("Warning: AI response did not contain the expected '---SPLIT---' separator.")
            # Return the raw response in both parts for debugging
            return response_text, "Could not parse response."

    except Exception as e:
        print(f"An error occurred during content generation: {e}")
        # Re-raise the exception to be caught by the main workflow
        raise e

    # This part should not be reached if an exception occurs
    return "Error during generation.", "Error during generation."