# This file will contain the Content Generation Agent.
# This agent will take a qualified Job object and generate
# tailored resume bullet points and a cover letter.
import json
import google.generativeai as genai
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
    if not config.google_api_key:
        print("Skipping content generation: GOOGLE_API_KEY not configured.")
        return "Content generation skipped due to missing API key.", "Content generation skipped."

    genai.configure(api_key=config.google_api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    print(f"Generating content for: {job.title}...")
    
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
    You are an expert career assistant. Your task is to help me apply for a job by generating tailored resume bullet points and a cover letter.
    {retry_prompt}
    **My Writing Style:**
    I prefer a professional, confident, and slightly informal tone. Here are some samples of my writing:
    ---
    {writing_samples}
    ---

    **My Resume:**
    Here is my current resume in JSON format. Use this to understand my experience and skills.
    ---
    {resume_json}
    ---

    **The Job I'm Applying For:**
    ---
    **Title:** {job.title}
    **Company:** {job.company}
    **Location:** {job.location}
    **Description:**
    {job.description}
    ---

    **Your Task:**
    You are an expert career coach writing on my behalf. Your goal is to create highly personalized, compelling application materials that will get me an interview.

    Based on all the information above, please generate the following two items:
    1.  **Resume Suggestions:** Write 2-3 powerful, action-oriented bullet points. Each bullet point MUST be concise and a **maximum of two lines long**. For each bullet, **explicitly connect** a specific achievement or skill from my resume to a key requirement in the job description. **You must use the quantifiable numbers and metrics** provided in my resume JSON to make the accomplishments more impactful. Use the STAR (Situation, Task, Action, Result) method to frame these accomplishments.
    2.  **Cover Letter:** Write a persuasive and engaging cover letter. Do not just summarize my resume. Instead, tell a story. Weave my experiences into a narrative that demonstrates I am the perfect candidate to solve this company's problems. Directly address the needs mentioned in the job description and use my writing style. **Crucially, you must replace all placeholders like [Your Name], [Your Address], etc., with the actual data provided in the JSON resume.**

    Please format your response with a clear separator between the two parts, like this:
    
    [Resume suggestions here]
    ---SPLIT---
    [Cover letter draft here]
    """

    try:
        response = model.generate_content(prompt)
        
        parts = response.text.split("---SPLIT---")
        if len(parts) == 2:
            resume_suggestions = parts[0].strip()
            cover_letter = parts[1].strip()
            print("Successfully generated content.")
            return resume_suggestions, cover_letter
        else:
            print("Warning: AI response did not contain the expected '---SPLIT---' separator.")
            # Return the raw response in both parts for debugging
            return response.text, "Could not parse response."

    except Exception as e:
        print(f"An error occurred during content generation: {e}")
        # Re-raise the exception to be caught by the main workflow
        raise e

    # This part should not be reached if an exception occurs
    return "Error during generation.", "Error during generation."