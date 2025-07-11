"""
Scraper Factory for dynamically creating platform-specific scrapers.
"""

from typing import Dict, Type, Optional, Any
from urllib.parse import urlparse
import logging

from .base import BaseScraper
from .linkedin_scraper import LinkedInScraper


class ScraperFactory:
    """
    Factory class for creating platform-specific scrapers.
    Supports automatic platform detection from URLs and manual platform selection.
    """
    
    # Registry of available scrapers
    _scrapers: Dict[str, Type[BaseScraper]] = {
        'linkedin': LinkedInScraper,
    }
    
    # URL patterns for automatic platform detection
    _url_patterns: Dict[str, str] = {
        'linkedin.com': 'linkedin',
    }
    
    @classmethod
    def register_scraper(cls, platform_name: str, scraper_class: Type[BaseScraper]) -> None:
        """
        Register a new scraper class for a platform.
        
        Args:
            platform_name: Name of the platform (e.g., 'indeed', 'glassdoor')
            scraper_class: Scraper class that extends BaseScraper
        """
        cls._scrapers[platform_name] = scraper_class
        logging.info(f"Registered scraper for platform: {platform_name}")
    
    @classmethod
    def register_url_pattern(cls, domain_pattern: str, platform_name: str) -> None:
        """
        Register a URL pattern for automatic platform detection.
        
        Args:
            domain_pattern: Domain pattern to match (e.g., 'indeed.com')
            platform_name: Platform name to associate with the pattern
        """
        cls._url_patterns[domain_pattern] = platform_name
        logging.info(f"Registered URL pattern '{domain_pattern}' for platform: {platform_name}")
    
    @classmethod
    def detect_platform(cls, url: str) -> Optional[str]:
        """
        Automatically detect the platform from a URL.
        
        Args:
            url: The URL to analyze
            
        Returns:
            Platform name if detected, None otherwise
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Check for exact domain matches
            for pattern, platform in cls._url_patterns.items():
                if pattern in domain:
                    return platform
                    
        except Exception as e:
            logging.error(f"Error parsing URL {url}: {e}")
            
        return None
    
    @classmethod
    def create_scraper(cls, driver, platform_name: str = None, url: str = None, 
                      **kwargs) -> Optional[BaseScraper]:
        """
        Create a scraper instance for the specified platform or URL.
        
        Args:
            driver: WebDriver instance
            platform_name: Explicit platform name (optional)
            url: URL to auto-detect platform from (optional)
            config: Configuration object containing platform configs
            **kwargs: Additional arguments to pass to the scraper
            
        Returns:
            Scraper instance or None if platform not found/supported
        """
        # Try explicit platform name first
        if platform_name:
            target_platform = platform_name
        # Fall back to URL detection
        elif url:
            target_platform = cls.detect_platform(url)
            if not target_platform:
                logging.warning(f"Could not detect platform from URL: {url}")
                return None
        else:
            logging.error("Either platform_name or url must be provided")
            return None
        
        # Check if we have a scraper for this platform
        if target_platform not in cls._scrapers:
            logging.error(f"No scraper available for platform: {target_platform}")
            return None
        
        scraper_class = cls._scrapers[target_platform]
        
        try:
            logger = logging.getLogger(f"scraper.{target_platform}")
            
            scraper = scraper_class(
                driver=driver,
                logger=logger,
                **kwargs
            )
            
            logging.info(f"Created {target_platform} scraper successfully")
            return scraper
            
        except Exception as e:
            logging.error(f"Failed to create {target_platform} scraper: {e}")
            return None
    
    @classmethod
    def get_available_platforms(cls) -> list[str]:
        """
        Get list of all available platform names.
        
        Returns:
            List of platform names
        """
        return list(cls._scrapers.keys())
    
    @classmethod
    def is_platform_supported(cls, platform_name: str) -> bool:
        """
        Check if a platform is supported.
        
        Args:
            platform_name: Name of the platform to check
            
        Returns:
            True if platform is supported, False otherwise
        """
        return platform_name in cls._scrapers
    
    @classmethod
    def validate_url_for_platform(cls, url: str, platform_name: str) -> bool:
        """
        Validate if a URL is compatible with a specific platform.
        
        Args:
            url: URL to validate
            platform_name: Platform to validate against
            
        Returns:
            True if URL is valid for the platform, False otherwise
        """
        if platform_name not in cls._scrapers:
            return False
            
        scraper_class = cls._scrapers[platform_name]
        
        # Create a temporary instance to use the validation method
        # We pass None for driver since we only need URL validation
        try:
            temp_scraper = scraper_class(driver=None)
            return temp_scraper.validate_url(url)
        except Exception:
            # If we can't create the scraper, assume URL is invalid
            return False 