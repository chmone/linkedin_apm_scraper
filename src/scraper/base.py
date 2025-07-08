from abc import ABC, abstractmethod
from typing import List, Iterator, Dict, Any, Optional
# We will define the Job data structure in a separate file
from .models import Job 

class BaseScraper(ABC):
    """
    Abstract base class for all job site scrapers.
    Defines the common interface for scraping job data from various platforms.
    """
    
    def __init__(self, driver, platform_config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize the scraper with a WebDriver and platform-specific configuration.
        
        Args:
            driver: WebDriver instance for browser automation
            platform_config: Platform-specific configuration dictionary
            **kwargs: Additional platform-specific arguments
        """
        self.driver = driver
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