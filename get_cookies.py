#!/usr/bin/env python3

import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def get_linkedin_cookies():
    """
    Opens LinkedIn in a browser window for manual login, then saves cookies.
    """
    print("🔑 LinkedIn Cookie Extraction Tool")
    print("=" * 50)
    
    # Setup Chrome with visible window for manual login
    options = Options()
    options.add_argument('--window-size=1920,1080')
    # Remove headless mode so you can see and interact with the browser
    
    driver = webdriver.Chrome(options=options)
    
    try:
        print("🌐 Opening LinkedIn login page...")
        driver.get("https://www.linkedin.com/login")
        
        print("\n📋 Instructions:")
        print("1. Complete the login process manually in the browser window")
        print("2. Navigate to a job search page (e.g., https://www.linkedin.com/jobs/)")
        print("3. Make sure you're fully logged in and can see job listings")
        print("4. Come back to this terminal and press ENTER when ready")
        
        # Wait for user to complete login
        input("\nPress ENTER after you've logged in and are on a job page...")
        
        print("\n💾 Extracting cookies...")
        cookies = driver.get_cookies()
        
        # Save cookies to file
        with open('cookies.json', 'w') as file:
            json.dump(cookies, file, indent=2)
        
        print(f"✅ Successfully saved {len(cookies)} cookies to cookies.json")
        
        # Take a screenshot to verify login state
        driver.save_screenshot('login_verification.png')
        print("📸 Saved verification screenshot as 'login_verification.png'")
        
        # Show current page info
        print(f"\n📄 Current page: {driver.title}")
        print(f"🔗 URL: {driver.current_url}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        print("\n🔄 Closing browser...")
        driver.quit()
        print("✨ Done!")

if __name__ == '__main__':
    get_linkedin_cookies() 