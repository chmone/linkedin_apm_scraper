# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies required for headless Chrome
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container at /app
COPY src/ .

# Define environment variables
# Note: These should be passed in at runtime, not hardcoded
ENV GOOGLE_API_KEY=""
ENV TELEGRAM_BOT_TOKEN=""
ENV TELEGRAM_CHAT_ID=""

# Copy configuration files
COPY search_urls.txt .
COPY cookies.json .
COPY resume.json .
COPY ideal_job_profile.txt .
COPY writing_style_samples/ ./writing_style_samples/

# Run main.py when the container launches
CMD ["python", "-u", "main.py"] 