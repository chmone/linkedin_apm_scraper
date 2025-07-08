from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime

@dataclass
class Job:
    """
    A data class to hold structured information about a job posting.
    Supports platform-agnostic core fields and platform-specific extensions.
    """
    # Core fields (required for all platforms)
    title: str
    company: str
    location: str
    description: str
    url: str
    
    # Metadata fields
    platform: str = ""  # Platform where the job was found (linkedin, indeed, etc.)
    search_url: str = ""  # Original search URL that led to this job
    scraped_at: datetime = field(default_factory=datetime.now)
    
    # Optional fields that may not be available on all platforms
    salary_range: Optional[str] = None
    job_type: Optional[str] = None  # Full-time, Part-time, Contract, etc.
    experience_level: Optional[str] = None  # Entry, Mid, Senior, etc.
    company_size: Optional[str] = None
    industry: Optional[str] = None
    remote_option: Optional[str] = None  # Remote, Hybrid, On-site
    posted_date: Optional[str] = None
    
    # Platform-specific additional data
    platform_data: Dict[str, Any] = field(default_factory=dict)
    
    def get_platform_field(self, field_name: str, default: Any = None) -> Any:
        """
        Get a platform-specific field value.
        
        Args:
            field_name: Name of the platform-specific field
            default: Default value if field doesn't exist
            
        Returns:
            Field value or default
        """
        return self.platform_data.get(field_name, default)
    
    def set_platform_field(self, field_name: str, value: Any) -> None:
        """
        Set a platform-specific field value.
        
        Args:
            field_name: Name of the platform-specific field
            value: Value to set
        """
        self.platform_data[field_name] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the job object to a dictionary for serialization.
        
        Returns:
            Dictionary representation of the job
        """
        return {
            'title': self.title,
            'company': self.company,
            'location': self.location,
            'description': self.description,
            'url': self.url,
            'platform': self.platform,
            'search_url': self.search_url,
            'scraped_at': self.scraped_at.isoformat(),
            'salary_range': self.salary_range,
            'job_type': self.job_type,
            'experience_level': self.experience_level,
            'company_size': self.company_size,
            'industry': self.industry,
            'remote_option': self.remote_option,
            'posted_date': self.posted_date,
            'platform_data': self.platform_data
        }