from abc import ABC, abstractmethod
from typing import List, Iterator, Dict, Any, Optional
# We will define the Job data structure in a separate file
from .models import Job 
import logging
import os
from datetime import datetime

class BaseScraper(ABC):
    """
    Abstract base class for all job site scrapers.
    Defines the common interface for scraping job data from various platforms.
    """
    
    def __init__(self, driver, logger: logging.Logger, platform_config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize the scraper with a WebDriver and platform-specific configuration.
        
        Args:
            driver: WebDriver instance for browser automation
            logger: Logger instance for logging
            platform_config: Platform-specific configuration dictionary
            **kwargs: Additional platform-specific arguments
        """
        self.driver = driver
        self.logger = logger
        self.platform_config = platform_config or {}
        self.platform_name = self.__class__.__name__.replace('Scraper', '').lower()
    
    @abstractmethod
    def scrape(self, url: str) -> Iterator[Job]:
        """
        The core method to perform the scraping from a given URL.
        This should be implemented by all concrete scraper classes.

        Args:
            url: The URL to scrape job listings from.

        Returns:
            An iterator of Job data objects.
        """
        pass
    
    @abstractmethod
    def authenticate(self) -> bool:
        """
        Perform platform-specific authentication.
        
        Returns:
            True if authentication was successful, False otherwise.
        """
        pass
    
    def get_platform_name(self) -> str:
        """
        Get the name of the job platform this scraper handles.
        
        Returns:
            String name of the platform (e.g., 'linkedin', 'indeed', 'glassdoor')
        """
        return self.platform_name
    
    def validate_url(self, url: str) -> bool:
        """
        Validate if the provided URL is compatible with this scraper.
        Override in platform-specific scrapers for URL validation.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid for this platform, False otherwise
        """
        return True  # Default implementation accepts any URL 

    def take_screenshot(self, name: str) -> None:
        """
        Takes a screenshot and saves it to the screenshots directory.
        
        Args:
            name: A descriptive name for the screenshot file.
        """
        try:
            # Ensure the screenshot directory exists
            screenshots_dir = "screenshots"
            os.makedirs(screenshots_dir, exist_ok=True)
            
            # Create a unique filename
            filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(screenshots_dir, filename)
            
            # Save the screenshot
            self.driver.save_screenshot(filepath)
            self.logger.info(f"Saved screenshot to {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to take screenshot: {e}") 