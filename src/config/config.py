import threading
import os
import json
from dotenv import load_dotenv
import logging

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
        self.telegram_api_key = os.getenv("TELEGRAM_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")

        self.search_urls = self._load_file("search_urls.txt").splitlines()
        self.cookies_file = "cookies.json"  # Store the path, not the content
        self.resume_data = json.loads(self._load_file("resume.json"))
        self.ideal_job_profile = self._load_file("ideal_job_profile.txt")
        self.writing_style_samples = self._load_writing_samples("writing_style_samples")
        
        # Load Google API Key from environment variables
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        if not self.google_api_key:
            logging.warning("GOOGLE_API_KEY environment variable not set.")

        # Load Telegram credentials from environment variables
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logging.warning("Telegram credentials (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) are not fully set.")

        print("Configuration loaded.")

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
            print(f"Warning: {filename} not found or is invalid.")
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

if __name__ == '__main__':
    # Create dummy files for testing
    os.makedirs("writing_style_samples", exist_ok=True)
    with open(".env", "w") as f:
        f.write("TELEGRAM_API_KEY=dummy_telegram_key\n")
        f.write("GOOGLE_API_KEY=dummy_llm_key\n")
    with open("search_urls.txt", "w") as f:
        f.write("https://www.linkedin.com/jobs/search/?keywords=product%20manager\n")
    with open("cookies.json", "w") as f:
        f.write('{"name": "li_at", "value": "dummy_cookie"}')
    with open("resume.json", "w") as f:
        f.write('{"experience": [{"title": "PM"}]}')
    with open("ideal_job_profile.txt", "w") as f:
        f.write("Looking for a fast-paced environment.")
    with open("writing_style_samples/sample1.txt", "w") as f:
        f.write("This is my writing style.")

    # Proof that it works
    config = Config.get_instance()
    print(f"Telegram Key: {config.telegram_api_key}")
    print(f"Google API Key: {config.google_api_key}")
    print(f"Search URLs: {config.search_urls}")
    print(f"Resume: {config.resume_data}")
    print(f"Writing Samples: {config.writing_style_samples}")

    # Clean up dummy files
    os.remove(".env")
    os.remove("search_urls.txt")
    os.remove("cookies.json")
    os.remove("resume.json")
    os.remove("ideal_job_profile.txt")
    os.remove("writing_style_samples/sample1.txt")
    os.rmdir("writing_style_samples") 