import os
import json
import pytest
from unittest.mock import MagicMock, patch

from src.scraper.models import Job
from src.main import main
from src.config.config import Config
# We no longer need to import the real scraper
# from src.scraper.linkedin_scraper import LinkedInScraper 

@pytest.fixture
def test_config(tmp_path, monkeypatch):
    """
    Creates a temporary configuration for testing purposes.
    """
    # Create dummy config files with valid LinkedIn URL
    (tmp_path / "search_urls.txt").write_text("https://www.linkedin.com/jobs/search/?keywords=product%20manager")
    (tmp_path / "cookies.json").write_text(json.dumps([{"name": "li_at", "value": "dummy"}]))
    (tmp_path / "resume.json").write_text(json.dumps({"experience": "Product Manager"}))
    (tmp_path / "ideal_job_profile.txt").write_text("An ideal job.")
    (tmp_path / "writing_style_samples").mkdir()
    (tmp_path / "writing_style_samples/sample1.txt").write_text("This is my writing style.")

    # Mock environment variables
    monkeypatch.setenv("GOOGLE_API_KEY", "test_google_key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_bot_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    # The Config class reads from the CWD, so we change it for the test.
    monkeypatch.chdir(tmp_path)

    # Since main() creates its own Config instance, we don't need to return one.
    # We just need the environment to be set up correctly.

def test_full_pipeline_with_mocks(test_config):
    """
    Tests the full pipeline from the main() entrypoint with mocked external services.
    - Mocks the LinkedInScraper to avoid network calls.
    - Mocks the generative AI models to avoid API calls and control output.
    - Mocks the TelegramNotifier to prevent sending actual messages.
    """
    # 1. Define mock data and return values
    mock_job_1 = Job(title="Associate Product Manager", company="Company A", url="http://example.com/1", description="Desc 1", location="Remote", platform="linkedin")
    mock_job_2 = Job(title="Product Manager", company="Company B", url="http://example.com/2", description="Desc 2", location="New York, NY", platform="linkedin")
    mock_jobs = [mock_job_1, mock_job_2]

    # 2. Set up patches for all external services
    with patch('src.main.setup_chrome_driver') as MockDriverSetup, \
         patch('src.main.ScraperFactory.create_scraper') as MockScraperFactory, \
         patch('openai.OpenAI') as MockOpenAIClient, \
         patch('src.main.TelegramNotifier') as MockNotifier:

        # Configure the return values for each mock
        mock_driver = MagicMock()
        MockDriverSetup.return_value = mock_driver
        
        mock_scraper_instance = MagicMock()
        mock_scraper_instance.scrape.return_value = mock_jobs
        mock_scraper_instance.validate_url.return_value = True  # Always validate URLs
        MockScraperFactory.return_value = mock_scraper_instance
        
        # Mock OpenAI client for all agents (validation, generation, review)
        mock_openai_client = MockOpenAIClient.return_value
        
        # Set up responses for different API calls
        # 1st call: Validation for first job (YES)
        # 2nd call: Validation for second job (NO) 
        # 3rd call: Generation for approved job
        # 4th call: Review for generated content
        mock_response_1 = MagicMock()
        mock_response_1.choices[0].message.content = "YES"
        
        mock_response_2 = MagicMock()
        mock_response_2.choices[0].message.content = "NO"
        
        mock_response_3 = MagicMock()
        mock_response_3.choices[0].message.content = "Resume points---SPLIT---Cover letter"
        
        mock_response_4 = MagicMock()
        mock_response_4.choices[0].message.content = "YES"
        
        mock_openai_client.chat.completions.create.side_effect = [
            mock_response_1,  # First job validation: YES
            mock_response_2,  # Second job validation: NO
            mock_response_3,  # Content generation for first job
            mock_response_4   # Content review: YES
        ]

        # Get a reference to the notifier instance for assertion
        notifier_instance = MockNotifier.return_value

        # 3. Run the main function
        main()

        # 4. Assert that the external services were called correctly
        mock_scraper_instance.scrape.assert_called()
        
        # OpenAI client should be called 4 times:
        # 2 for validation (both jobs), 1 for generation, 1 for review
        assert mock_openai_client.chat.completions.create.call_count == 4

        # Notifier should only be called once with the final message for the approved job
        notifier_instance.send_message.assert_called_once()
        
        # Optional: Check the content of the message sent
        sent_message = notifier_instance.send_message.call_args[0][0]
        assert "Associate Product Manager" in sent_message
        # The second job should be rejected so it shouldn't appear in the final message
        assert "Company B" not in sent_message 