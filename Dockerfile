# Use Ubuntu as base image
FROM ubuntu:22.04

# Set non-interactive frontend
ENV DEBIAN_FRONTEND=noninteractive

# Install Python, Chrome, and dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    gnupg \
    curl \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    unzip \
    --no-install-recommends && \
    # Install Chrome
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    # Get Chrome version and install matching ChromeDriver from Chrome for Testing
    CHROME_VERSION=$(google-chrome --version | awk '{print $3}') && \
    echo "Chrome version: $CHROME_VERSION" && \
    # Use Chrome for Testing API for newer Chrome versions
    CHROMEDRIVER_URL=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json" | \
    python3 -c "import sys, json; data=json.load(sys.stdin); versions=[v for v in data['versions'] if v['version']=='$CHROME_VERSION']; print(versions[0]['downloads']['chromedriver'][0]['url'] if versions else '')") && \
    if [ -n "$CHROMEDRIVER_URL" ]; then \
        echo "Downloading ChromeDriver from: $CHROMEDRIVER_URL" && \
        wget -q "$CHROMEDRIVER_URL" -O chromedriver.zip && \
        unzip chromedriver.zip && \
        mv chromedriver-linux64/chromedriver /usr/local/bin/ && \
        chmod +x /usr/local/bin/chromedriver && \
        rm -rf chromedriver.zip chromedriver-linux64; \
    else \
        echo "No matching ChromeDriver found, relying on Selenium Manager"; \
    fi && \
    # Clean up
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements and install Python packages in virtual environment
COPY requirements.txt .
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Ensure virtual environment is used
ENV PATH="/opt/venv/bin:$PATH"

# Copy application files
COPY src/ ./src/
COPY search_urls.txt .
COPY cookies.json .
COPY resume.json .
COPY ideal_job_profile.txt .
COPY writing_style_samples/ ./writing_style_samples/

# Create a non-root user for security (but run as root for Chrome compatibility)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
# Run as root to avoid Chrome permission issues in Docker containers
# USER appuser

# Run the application directly
CMD ["python3", "-u", "src/main.py"] 