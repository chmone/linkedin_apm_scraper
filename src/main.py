# This is the main orchestrator for the AI-Powered Job Scraper.

import time
import logging
import os
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from config.config import load_config
from scraper.factory import ScraperFactory
from agents.workflow import run_workflow
from notifier.telegram_notifier import TelegramNotifier

def is_github_actions():
    """Detect if running in GitHub Actions environment."""
    return os.getenv('GITHUB_ACTIONS') == 'true' or os.getenv('CI') == 'true'

def is_docker_environment():
    """Detect if running in Docker container."""
    return os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER') == 'true'

def cleanup_chrome_processes():
    """Aggressively clean up Chrome processes."""
    try:
        # Kill any existing Chrome/ChromeDriver processes
        subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, text=True)
        subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, text=True)
        subprocess.run(['pkill', '-f', 'chromium'], capture_output=True, text=True)
        
        # Wait a moment for processes to clean up
        time.sleep(2)
        
        logging.info("Chrome process cleanup completed")
    except Exception as e:
        logging.warning(f"Chrome process cleanup failed: {e}")

def get_chrome_options_tier1():
    """Minimal Chrome configuration - Tier 1."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-default-apps")
    return options

def get_chrome_options_tier2():
    """Aggressive Chrome configuration - Tier 2 for CI/CD."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-images")
    options.add_argument("--disable-javascript")
    options.add_argument("--disable-plugins-discovery")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-crash-reporter")
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    options.add_argument("--silent")
    options.add_argument("--remote-debugging-port=0")  # Dynamic port allocation
    return options

def get_chrome_options_tier3():
    """Single-process Chrome configuration - Tier 3 for extreme cases."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox") 
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--single-process")  # Run everything in single process
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-features=VizDisplayCompositor,TranslateUI")
    options.add_argument("--disable-ipc-flooding-protection")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-images")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-crash-reporter")
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    options.add_argument("--silent")
    options.add_argument("--memory-pressure-off")
    options.add_argument("--max_old_space_size=4096")
    return options

def setup_chrome_driver(headless: bool = True) -> webdriver.Chrome:
    """
    Set up Chrome WebDriver with comprehensive Docker optimizations and fallback strategies.
    Optimized for GitHub Actions and containerized environments.
    """
    
    # Environment detection
    is_ci = is_github_actions()
    is_docker = is_docker_environment()
    
    logging.info(f"Environment: GitHub Actions={is_ci}, Docker={is_docker}")
    
    # Clean up any existing processes
    cleanup_chrome_processes()
    
    # Determine configuration strategy
    config_tiers = []
    
    if is_ci:
        # GitHub Actions - try aggressive configs first
        config_tiers = [
            ("Tier 3 - Single Process", get_chrome_options_tier3),
            ("Tier 2 - Aggressive CI/CD", get_chrome_options_tier2),
            ("Tier 1 - Minimal", get_chrome_options_tier1)
        ]
    else:
        # Local/Docker - try minimal first
        config_tiers = [
            ("Tier 1 - Minimal", get_chrome_options_tier1),
            ("Tier 2 - Aggressive CI/CD", get_chrome_options_tier2),
            ("Tier 3 - Single Process", get_chrome_options_tier3)
        ]
    
    # Try each configuration tier
    for tier_name, get_options_func in config_tiers:
        try:
            logging.info(f"Attempting Chrome startup with {tier_name}")
            
            chrome_options = get_options_func()
            
            # Force headless mode if specified
            if headless and not any('--headless' in arg for arg in chrome_options.arguments):
                chrome_options.add_argument("--headless=new")
            
            # Create service
            service = Service()
            
            # Attempt to create driver
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            logging.info(f"✅ Chrome started successfully with {tier_name}")
            return driver
            
        except Exception as e:
            logging.warning(f"❌ {tier_name} failed: {str(e)}")
            
            # Clean up between attempts
            cleanup_chrome_processes()
            
            # Wait before next attempt
            time.sleep(3)
            
            # If this was the last tier, re-raise the exception
            if tier_name == config_tiers[-1][0]:
                logging.error(f"All Chrome configuration tiers failed. Last error: {str(e)}")
                raise e
            
            # Continue to next tier
            continue
    
    # Should never reach here, but just in case
    raise Exception("All Chrome configuration strategies failed")


def scrape_platform_jobs(driver: webdriver.Chrome, platform_name: str, urls: list[str], config, notifier) -> list:
    """
    Scrape jobs from a specific platform using the appropriate scraper.
    
    Args:
        driver: WebDriver instance
        platform_name: Name of the platform to scrape
        urls: List of URLs to scrape from this platform
        config: Configuration object
        notifier: Notification service
        
    Returns:
        List of scraped jobs
    """
    all_jobs = []
    
    # Get platform configuration
    platform_config = config.get_platform_config(platform_name)
    if not platform_config:
        logging.warning(f"No configuration found for platform: {platform_name}")
        return all_jobs
    
    # Create platform-specific scraper using factory
    scraper_kwargs = {}
    if platform_name == 'linkedin':
        # LinkedIn-specific arguments for backward compatibility
        scraper_kwargs.update({
            'linkedin_email': config.linkedin_email,
            'linkedin_password': config.linkedin_password,
            'notifier': notifier
        })
    
    scraper = ScraperFactory.create_scraper(
        driver=driver,
        platform_name=platform_name,
        config=config,
        **scraper_kwargs
    )
    
    if not scraper:
        logging.error(f"Failed to create scraper for platform: {platform_name}")
        return all_jobs
    
    logging.info(f"Starting to scrape {len(urls)} URLs from {platform_name}")
    
    # Scrape jobs from each URL for this platform
    for url in urls:
        logging.info(f"Scraping jobs from {platform_name} URL: {url}")
        try:
            # Validate URL for this platform
            if not scraper.validate_url(url):
                logging.warning(f"URL {url} is not valid for platform {platform_name}")
                continue
                
            jobs_from_url = list(scraper.scrape(url))
            all_jobs.extend(jobs_from_url)
            
            logging.info(f"Found {len(jobs_from_url)} jobs from {url}")
            
            # Add delay between URLs to avoid rate limiting
            if len(urls) > 1:
                delay = platform_config.rate_limit_config.get('page_delay', 5)
                time.sleep(delay)
                
        except Exception as e:
            logging.error(f"Failed to scrape from {url}: {e}", exc_info=True)
    
    logging.info(f"Completed scraping {platform_name}. Found {len(all_jobs)} total jobs.")
    return all_jobs


def main():
    """
    The main function to run the AI-Powered Job Scraper with multi-platform support.
    """
    import os
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.getLogger("httpx").setLevel(logging.WARNING)

    config = load_config()
    
    # Set up WebDriver
    driver = setup_chrome_driver(headless=config.headless)
    
    try:
        # Set up notification service
        notifier = TelegramNotifier(config)
        
        # Get all URLs grouped by platform
        all_urls = config.get_all_search_urls()
        if not all_urls:
            logging.warning("No search URLs configured. Please check your configuration.")
            return
        
        # Group URLs by platform
        platform_urls = {}
        for url, platform_name in all_urls:
            if platform_name not in platform_urls:
                platform_urls[platform_name] = []
            platform_urls[platform_name].append(url)
        
        logging.info(f"Starting job scraping across {len(platform_urls)} platforms...")
        
        # Scrape jobs from each platform
        all_jobs = []
        for platform_name, urls in platform_urls.items():
            logging.info(f"Processing platform: {platform_name}")
            
            platform_jobs = scrape_platform_jobs(driver, platform_name, urls, config, notifier)
            all_jobs.extend(platform_jobs)
            
            # Add delay between platforms to avoid overwhelming any single platform
            if len(platform_urls) > 1:
                time.sleep(5)

        if not all_jobs:
            logging.info("No new jobs were scraped from any platform.")
        else:
            logging.info(f"Scraped a total of {len(all_jobs)} jobs across all platforms. Starting AI workflow...")
            
            # Process each job through the AI workflow
            for job in all_jobs:
                logging.info(f"Processing job: {job.title} at {job.company} ({job.platform})")
                
                message_groups = run_workflow(job, config)
                if message_groups:
                    for group in message_groups:
                        for message in group:
                            notifier.send_message(message)
                            time.sleep(1)  # Small delay between parts of the message
                        # Add a delay between notifications to avoid rate limiting
                        time.sleep(5)

        print("AI-Powered Job Scraper finished successfully.")
        
    except Exception as e:
        logging.error(f"An error occurred in the main workflow: {e}", exc_info=True)
    finally:
        logging.info("Closing the WebDriver.")
        if driver:
            driver.quit()


if __name__ == '__main__':
    main() 