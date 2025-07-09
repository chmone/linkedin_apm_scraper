# Use the official Selenium image which has Chrome and a non-root user configured.
FROM selenium/standalone-chrome:latest

# Switch to root user to install Python
USER root

# Install Python and pip
RUN apt-get update && apt-get install -y python3 python3-pip --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY src/ .
COPY search_urls.txt .
COPY cookies.json .
COPY resume.json .
COPY ideal_job_profile.txt .
COPY writing_style_samples/ ./writing_style_samples/

# Switch back to the non-root user for security
USER seluser

# Run the Python script when the container launches
CMD ["python3", "-u", "main.py"] 