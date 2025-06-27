# This file will contain the Job Validation Agent.
# This agent will take a Job object and the ideal_job_profile.txt
# and determine if the job is a good fit.

def validate_job(job, ideal_profile):
    Uses an LLM to compare the job details against the ideal profile.
    Returns True if it's a good fit, False otherwise.
    # For now, we'll assume all jobs are a good fit to test the pipeline.
    return True
