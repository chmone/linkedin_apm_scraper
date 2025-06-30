# This is the main orchestrator for the AI Job Scraper.

import logging
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

from config.config import Config
from scraper.linkedin_scraper import LinkedInScraper
from agents.workflow import run_workflow
from notifier.telegram_notifier import TelegramNotifier

def main():
    """
    Main function to run the job scraping and processing workflow.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    driver = None  # Initialize driver to None
    try:
        # Get configuration
        config = Config.get_instance()

        # Initialize WebDriver
        chrome_options = ChromeOptions()
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        driver = webdriver.Chrome(options=chrome_options)

        # 1. Scrape Jobs
        logging.info("Starting job scraping...")
        scraper = LinkedInScraper(driver=driver, cookies_path=config.cookies_file)
        
        all_jobs = []
        for url in config.search_urls:
            logging.info(f"Scraping jobs from URL: {url}")
            try:
                for job in scraper.scrape(url):
                    all_jobs.append(job)
            except Exception as e:
                logging.error(f"Failed to scrape from {url}: {e}", exc_info=True)

        if not all_jobs:
            logging.info("No jobs were scraped.")
        else:
            logging.info(f"Scraped a total of {len(all_jobs)} jobs. Starting AI workflow...")
            for job in all_jobs:
                run_workflow(job, config)

        print("AI Job Scraper finished successfully.")
    except Exception as e:
        logging.error(f"An error occurred in the main workflow: {e}", exc_info=True)
    finally:
        if driver:
            logging.info("Closing the WebDriver.")
            driver.quit()

if __name__ == "__main__":
    main() 