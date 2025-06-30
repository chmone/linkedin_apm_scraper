# This is the main orchestrator for the AI Job Scraper.

import logging
import time

from config.config import load_config
from scraper.linkedin_scraper import LinkedInScraper
from agents.workflow import run_workflow
from notifier.telegram_notifier import TelegramNotifier

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def main():
    """
    The main function to run the LinkedIn job scraper and AI workflow.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.getLogger("httpx").setLevel(logging.WARNING)

    config = load_config()
    
    chrome_options = Options()
    chrome_options.add_argument("--log-level=3") # Suppress logs except fatal ones.
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging']) # Suppress DevTools messages
    chrome_options.add_argument("--headless") # Always run in headless mode for production
    
    # These options are generally good for stability in Docker/CI environments
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # 1. Scrape Jobs
        logging.info("Starting job scraping...")
        scraper = LinkedInScraper(driver=driver, cookies_path=config.cookies_file)
        
        all_jobs = []
        for url in config.search_urls:
            logging.info(f"Scraping jobs from URL: {url}")
            try:
                all_jobs.extend(scraper.scrape(url))
            except Exception as e:
                logging.error(f"Failed to scrape from {url}: {e}", exc_info=True)

        if not all_jobs:
            logging.info("No new jobs were scraped.")
        else:
            logging.info(f"Scraped a total of {len(all_jobs)} jobs. Starting AI workflow...")
            notifier = TelegramNotifier(config)
            
            for job in all_jobs:
                message_groups = run_workflow(job, config)
                if message_groups:
                    for group in message_groups:
                        for message in group:
                            notifier.send_message(message)
                            time.sleep(1) # Small delay between parts of the message
                        # Add a delay between notifications to avoid rate limiting
                        time.sleep(5)

        print("AI Job Scraper finished successfully.")
    except Exception as e:
        logging.error(f"An error occurred in the main workflow: {e}", exc_info=True)
    finally:
        logging.info("Closing the WebDriver.")
        driver.quit()

if __name__ == '__main__':
    main() 