import threading
import os
import json
from dotenv import load_dotenv
import logging
from typing import Dict, List, Any, Optional

class PlatformConfig:
    """Configuration for a specific job platform."""
    
    def __init__(self, platform_name: str, config_data: Dict[str, Any]):
        self.platform_name = platform_name
        self.enabled = config_data.get('enabled', True)
        self.search_urls = config_data.get('search_urls', [])
        self.auth_config = config_data.get('auth', {})
        self.scraper_config = config_data.get('scraper_settings', {})
        self.rate_limit_config = config_data.get('rate_limits', {})
        
    def get_auth_setting(self, key: str, default: Any = None) -> Any:
        """Get platform-specific authentication setting."""
        return self.auth_config.get(key, default)
    
    def get_scraper_setting(self, key: str, default: Any = None) -> Any:
        """Get platform-specific scraper setting."""
        return self.scraper_config.get(key, default)

class Config:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                # Another thread could have created the instance
                # before this one acquired the lock.
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls):
        """Static access method."""
        if cls._instance is None:
            cls()
        return cls._instance

    def __init__(self):
        """
        The constructor should not be called more than once.
        """
        # This check is to prevent re-initialization
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        self._load_config()

    def _load_config(self):
        """Loads all configuration data from files."""
        # Load environment variables from .env file
        load_dotenv()
        
        # Global settings
        self.headless = os.getenv("HEADLESS", "false").lower() == "true"
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.telegram_api_key = os.getenv("TELEGRAM_API_KEY")
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # LinkedIn credentials
        self.linkedin_email = os.getenv("LINKEDIN_EMAIL")
        self.linkedin_password = os.getenv("LINKEDIN_PASSWORD")
        
        # Load platform configurations
        self.platforms = {}
        self._load_platform_configs()
        
        # Backward compatibility: Load LinkedIn-specific settings if they exist
        self._load_legacy_settings()
        
        # Load AI and notification settings
        self.resume_data = json.loads(self._load_file("resume.json"))
        self.ideal_job_profile = "ideal_job_profile.txt"
        self.writing_style_samples = self._load_writing_samples("writing_style_samples")
        
        # Validate configuration
        self._validate_config()
        
        print("Configuration loaded.")

    def _load_platform_configs(self):
        """Load platform-specific configurations."""
        # Try to load from platforms.json first (new format)
        platforms_config = self._load_json_file("platforms.json")
        
        if platforms_config:
            for platform_name, platform_data in platforms_config.items():
                self.platforms[platform_name] = PlatformConfig(platform_name, platform_data)
        else:
            # Create default LinkedIn configuration if no platforms.json exists
            self._create_default_linkedin_config()
    
    def _create_default_linkedin_config(self):
        """Create default LinkedIn configuration for backward compatibility."""
        search_urls = self._load_file("search_urls.txt").splitlines()
        linkedin_password = os.getenv("LINKEDIN_PASSWORD")
        linkedin_email = os.getenv("LINKEDIN_EMAIL")
        
        linkedin_config_data = {
            'enabled': True,
            'search_urls': search_urls,
            'auth': {
                'cookies_path': 'cookies.json',
                'email': linkedin_email,
                'password': linkedin_password,
                'use_cookies': True,
                'use_password': bool(linkedin_password)
            },
            'scraper_settings': {
                'headless': self.headless,
                'wait_timeout': 10,
                'scroll_pause': 0.5,
                'click_pause': 2
            },
            'rate_limits': {
                'request_delay': 1,
                'page_delay': 5
            }
        }
        
        self.platforms['linkedin'] = PlatformConfig('linkedin', linkedin_config_data)
    
    def _load_legacy_settings(self):
        """Load legacy settings for backward compatibility."""
        # These are kept for backward compatibility with existing code
        self.linkedin_email = os.getenv("LINKEDIN_EMAIL")
        self.linkedin_password = os.getenv("LINKEDIN_PASSWORD")
        self.search_urls = self._load_file("search_urls.txt").splitlines()
        self.cookies_file = "cookies.json"

    def get_platform_config(self, platform_name: str) -> Optional[PlatformConfig]:
        """Get configuration for a specific platform."""
        return self.platforms.get(platform_name)
    
    def get_enabled_platforms(self) -> List[str]:
        """Get list of enabled platform names."""
        return [name for name, config in self.platforms.items() if config.enabled]
    
    def get_all_search_urls(self) -> List[tuple[str, str]]:
        """Get all search URLs with their associated platform names."""
        urls = []
        for platform_name, platform_config in self.platforms.items():
            if platform_config.enabled:
                for url in platform_config.search_urls:
                    urls.append((url, platform_name))
        return urls

    def _validate_config(self):
        """Validate the loaded configuration."""
        # Validate API keys
        if not self.openrouter_api_key:
            logging.warning("OPENROUTER_API_KEY environment variable not set.")

        # Validate Telegram settings
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logging.warning("Telegram credentials (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) are not fully set.")
        
        # Validate platform configurations
        enabled_platforms = self.get_enabled_platforms()
        if not enabled_platforms:
            logging.warning("No platforms are enabled in the configuration.")
        
        # Validate search URLs
        all_urls = self.get_all_search_urls()
        if not all_urls:
            logging.warning("No search URLs configured for any enabled platforms.")

    def _load_file(self, filename):
        """Loads a file from the root directory."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Warning: {filename} not found.")
            return ""

    def _load_json_file(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _load_directory_files(self, dirname):
        samples = {}
        if not os.path.isdir(dirname):
            print(f"Warning: Directory {dirname} not found.")
            return samples
            
        for filename in os.listdir(dirname):
            path = os.path.join(dirname, filename)
            if os.path.isfile(path):
                samples[filename] = self._load_file(path)
        return samples

    def _load_json(self, file_name):
        """Loads a JSON file from the root directory."""
        try:
            with open(file_name, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"Warning: {file_name} not found or is invalid.")
            return {}

    def _load_text(self, file_name):
        """Loads a text file from the root directory."""
        try:
            with open(file_name, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Warning: {file_name} not found.")
            return ""

    def _load_writing_samples(self, dirname):
        """Loads all writing samples from a directory."""
        samples = {}
        if not os.path.isdir(dirname):
            print(f"Warning: Directory {dirname} not found.")
            return samples
            
        for filename in os.listdir(dirname):
            path = os.path.join(dirname, filename)
            if os.path.isfile(path):
                samples[filename] = self._load_text(path)
        return samples

def load_config():
    """Factory function to get the config instance."""
    return Config.get_instance() 