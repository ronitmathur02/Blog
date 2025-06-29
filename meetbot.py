import time
import argparse
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from transcriber import record_and_transcribe
from summarizer import generate_summary
from mailer import send_summary_emails
import config
import requests
import undetected_chromedriver as uc

class GoogleMeetBot:
    def __init__(self):
        self.driver = None
        self.meet_url = None
        self.participants = []
        
    def setup_driver(self):
        try:
            print("Initializing Chrome with proper version matching...")
            
            user_data_dir = os.path.join(os.path.expanduser('~'), 'chrome-profile-undetected')
            os.makedirs(user_data_dir, exist_ok=True)
            
            # FIX: Specify the correct Chrome version to match your installed browser
            try:
                # First approach - specify version explicitly for undetected_chromedriver
                self.driver = uc.Chrome(
                    user_data_dir=user_data_dir,
                    browser_executable_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                    version_main=130  # Match your Chrome version (130.0.6723.117)
                )
                print("Chrome initialized successfully with version matching")
                return self.driver
            except Exception as uc_error:
                print(f"Undetected ChromeDriver failed: {uc_error}")
                print("Falling back to regular Selenium...")
                
                # Second approach - Use regular Selenium with webdriver_manager
                options = webdriver.ChromeOptions()
                options.add_argument(f"--user-data-dir={user_data_dir}")
                options.add_argument("--start-maximized")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_argument("--use-fake-ui-for-media-stream")  # Auto accept mic/cam
                options.add_argument("--enable-usermedia-screen-capturing")  # Enable screen capture
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option("useAutomationExtension", False)
                
                # Use WebDriverManager to get matching driver
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
                print("Chrome initialized successfully with Selenium WebDriver")
                return self.driver
        
        except Exception as e:
            print(f"All driver setup methods failed: {e}")
            raise
        
    def login_to_google(self):
        """Login to Google account with improved handling for security challenges."""
        try:
            # First check if already logged in by visiting a Google page
            print("Checking if already logged in...")
            self.driver.get("https://accounts.google.com")
            time.sleep(5)
            
            # Look for elements that indicate you're logged in
            current_url = self.driver.current_url
            
            if "myaccount.google.com" in current_url or "accounts.google.com/welcome" in current_url:
                print("Already logged in, proceeding to meeting")
                return
                
            # If not logged in, proceed with login
            print("Not logged in. Starting manual login process...")
            self.driver.get("https://accounts.google.com/signin")
            
            # Explicit wait for manual login
            print("\n" + "=" * 60)
            print("📲 MANUAL LOGIN REQUIRED 📲")
            print("=" * 60)
            print("1. Please log in MANUALLY in the browser window")
            print("2. Complete any security challenges Google presents")
            print("3. Make sure you're fully logged in before proceeding")
            print("4. You have 60 seconds to complete this process")
            print("=" * 60 + "\n")
            
            time.sleep(60)  # Wait for manual login
            
            # Check if login was successful
            if "myaccount.google.com" in self.driver.current_url or "accounts.google.com/signin/v2/challenge" in self.driver.current_url:
                print("Login successful or security challenge presented")
                # If there's a security challenge, give more time
                if "challenge" in self.driver.current_url:
                    print("Security challenge detected - please complete it")
                    time.sleep(30)  # Additional time for security challenge
            else:
                print("Login may not have been successful, but continuing anyway")
        
        except Exception as e:
            print(f"Error during Google login: {e}")
            print("Continuing despite login issues...")
        
    def join_meeting(self, meet_url):
        """Join the Google Meet with improved timeout handling."""
        try:
            # Clean up the URL if needed
            if "meet.google.com/meet.google.com" in meet_url:
                meet_url = meet_url.replace("meet.google.com/meet.google.com", "meet.google.com")
                
            self.meet_url = meet_url
            print(f"Navigating to meeting URL: {meet_url}")
            
            # Replace the current step loading approach with this:
            try:
                # Direct navigation with retries
                print("Navigating to meeting URL with retry mechanism...")
                max_retries = 3
                for attempt in range(1, max_retries+1):
                    try:
                        print(f"Navigation attempt {attempt}/{max_retries}...")
                        self.driver.get("https://www.google.com")  # First load a reliable page
                        time.sleep(3)
                        
                        # Use JavaScript navigation which may be less prone to timeout
                        print(f"Navigating to {meet_url} via JavaScript...")
                        self.driver.execute_script(f'window.location.replace("{meet_url}");')
                        
                        # Wait incrementally, checking for page elements
                        for i in range(1, 10):  # 50 seconds total (10 x 5)
                            print(f"Waiting for page elements... {i*5} seconds")
                            time.sleep(5)
                            
                            # Check if we're on the meeting page by looking for common elements
                            page_ready = False
                            try:
                                # Look for any of these elements that would indicate the page loaded
                                checks = [
                                    self.driver.find_elements(By.TAG_NAME, "video"),
                                    self.driver.find_elements(By.XPATH, "//button[contains(., 'Join')]"),
                                    self.driver.find_elements(By.XPATH, "//h1[contains(., 'Meeting')]")
                                ]
                                if any(checks):
                                    page_ready = True
                                    break
                            except:
                                pass
                                
                        if page_ready:
                            print("Meeting page elements found!")
                            break
                    except Exception as retry_error:
                        print(f"Attempt {attempt} failed: {retry_error}")
                        if attempt == max_retries:
                            print("All navigation attempts failed")
                        else:
                            print("Retrying...")
                            time.sleep(5)
            except Exception as e:
                print(f"All navigation approaches failed: {e}")
            
            # Take a screenshot to debug
            screenshot_path = os.path.join(os.getcwd(), "meeting_page.png")
            self.driver.save_screenshot(screenshot_path)
            print(f"Screenshot saved to: {screenshot_path}")
            
            print("Meeting page loaded, looking for join options...")
            
            # Try multiple approaches to find join button
            found_button = False
            
            # Try approach 1: JavaScript detection
            try:
                print("Using JavaScript to find any join buttons...")
                join_buttons = self.driver.execute_script("""
                    return Array.from(document.querySelectorAll('button')).filter(
                        btn => btn.textContent.toLowerCase().includes('join') ||
                        btn.getAttribute('aria-label')?.toLowerCase().includes('join')
                    );
                """)
                
                if join_buttons and len(join_buttons) > 0:
                    print(f"Found {len(join_buttons)} potential join buttons via JavaScript")
                    self.driver.execute_script("arguments[0].click();", join_buttons[0])
                    found_button = True
                    print("Clicked join button via JavaScript")
            except Exception as js_error:
                print(f"JavaScript approach failed: {js_error}")
            
            # Try approach 2: XPath selectors
            if not found_button:
                selectors = [
                    "//span[contains(text(), 'Join now')]/ancestor::button",
                    "//button[contains(., 'Join now')]",
                    "//div[contains(@role, 'button') and contains(., 'Join')]",
                    "//button[contains(@data-meeting-code, 'join')]"
                ]
                
                for selector in selectors:
                    try:
                        print(f"Trying selector: {selector}")
                        join_button = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        join_button.click()
                        found_button = True
                        print(f"Clicked join button with selector: {selector}")
                        break
                    except:
                        print(f"Selector {selector} failed")
            
            # Add after trying selectors in join_meeting:
            if not found_button:
                # Force continue by simulating a successful join
                print("Using 'force join' mode - assuming we're in the meeting")
                try:
                    # Click anywhere on the page to ensure focus
                    self.driver.find_element(By.TAG_NAME, "body").click()
                    # Take a screenshot to verify current state
                    self.driver.save_screenshot("force_join.png")
                    print("Force join mode activated - continuing as if joined")
                except:
                    print("Force join click failed - continuing anyway")
            
            if found_button:
                print("Join button clicked, waiting to enter meeting...")
                time.sleep(10)
                print("Joined the meeting successfully")
            else:
                # Don't raise exception, continue anyway (for testing)
                print("Could not find join button, but continuing for testing purposes")
            
        except Exception as e:
            print(f"Error joining meeting: {e}")
            screenshot_path = os.path.join(os.getcwd(), "join_error.png")
            try:
                self.driver.save_screenshot(screenshot_path)
                print(f"Error screenshot saved to: {screenshot_path}")
            except:
                pass
            # Don't raise the exception - continue anyway
            print("Continuing despite join meeting error...")
            
    def collect_participants(self):
        """Collect participant emails from the meeting."""
        try:
            print("Collecting participant information...")
            
            # Click on participant list button if available
            try:
                # Try multiple selectors for the participants button
                participant_selectors = [
                    "//button[contains(@aria-label, 'participants')]",
                    "//button[contains(@aria-label, 'Show everyone')]", 
                    "//div[contains(@aria-label, 'Show everyone')]",
                    "//button[contains(@data-tooltip-id, 'Show everyone')]",
                    "//div[@role='button' and contains(., 'participants')]",
                    "//span[contains(text(), 'participants')]/ancestor::button"
                ]
                
                found_button = False
                for selector in participant_selectors:
                    try:
                        participants_button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        participants_button.click()
                        print(f"Opened participants panel using selector: {selector}")
                        time.sleep(2)
                        found_button = True
                        break
                    except Exception as button_error:
                        continue
                
                if not found_button:
                    print("Could not find participants button, trying alternative approach...")
                    
                    # Try looking for a number that indicates participant count
                    try:
                        # Click element that shows participant count
                        count_element = self.driver.find_element(By.XPATH, 
                            "//div[contains(@class, 'uGOf1d') and contains(text(), '(')]")
                        count_element.click()
                        print("Clicked participant count element")
                        time.sleep(2)
                    except Exception as count_error:
                        print(f"Could not find participant count: {count_error}")
                        raise Exception("Cannot access participants panel")
                    
                # Extract participant information
                print("Extracting participant names...")
                
                # Take screenshot of participant panel for debugging
                self.driver.save_screenshot("participants_panel.png")
                print("Saved screenshot of participants panel")
                
                # Extract participants using JavaScript
                participants_data = self.driver.execute_script("""
                    // Find all elements that might contain participant info
                    const participantElements = document.querySelectorAll('[role="listitem"]');
                    const participants = [];
                    
                    // Process each element
                    participantElements.forEach(element => {
                        // Skip non-participant elements
                        if (!element.textContent || element.textContent.length < 2) {
                            return;
                        }
                        
                        // Get the name - different Google Meet versions use different structures
                        let name = '';
                        
                        // Try multiple approaches to get the name
                        const nameElement = element.querySelector('[data-participant-name], [data-tooltip], [aria-label]');
                        if (nameElement) {
                            name = nameElement.getAttribute('data-participant-name') || 
                                   nameElement.getAttribute('data-tooltip') || 
                                   nameElement.getAttribute('aria-label') || '';
                        }
                        
                        // If we couldn't get the name from attributes, use the text content
                        if (!name) {
                            name = element.textContent.trim();
                        }
                        
                        // Clean up the name
                        name = name.replace(/\\(You\\)/i, '')
                                   .replace(/\\(Host\\)/i, '')
                                   .replace(/\\(Meeting organizer\\)/i, '')
                                   .replace(/\\s+/g, ' ')
                                   .trim();
                                   
                        if (name) {
                            participants.push({
                                name: name,
                                isYou: element.textContent.includes('You'),
                                isHost: element.textContent.includes('Host') || 
                                        element.textContent.includes('organizer')
                            });
                        }
                    });
                    
                    return participants;
                """)
                
                # Process the participant data
                emails = []
                
                if participants_data and len(participants_data) > 0:
                    print(f"\nFound {len(participants_data)} participants:")
                    print("=" * 50)
                    
                    for idx, participant in enumerate(participants_data):
                        name = participant.get('name', 'Unknown')
                        is_you = participant.get('isYou', False)
                        is_host = participant.get('isHost', False)
                        
                        print(f"{idx + 1}. {name}" + 
                              (" (YOU)" if is_you else "") + 
                              (" (Host)" if is_host else ""))
                        
                        # For yourself, use the config email
                        if is_you:
                            emails.append(config.EMAIL_HOST_USER)
                            continue
                            
                        # For others, ask for email
                        name_parts = name.split()
                        suggested_email = f"{name_parts[0].lower()}"
                        if len(name_parts) > 1:
                            suggested_email += f".{name_parts[-1].lower()}"
                        suggested_email += "@gmail.com"
                        
                        want_email = input(f"\nInclude {name} in email recipients? (y/n): ").lower().startswith('y')
                        if want_email:
                            email = input(f"Enter email for {name} [default: {suggested_email}]: ").strip()
                            if not email:
                                email = suggested_email
                            emails.append(email)
                            print(f"Added {email} to recipients list")
                    
                    print("=" * 50)
                else:
                    print("No participants found in the panel")
            
            except Exception as panel_error:
                print(f"Error accessing participant panel: {panel_error}")
                
                # Fallback: Ask user to manually enter emails
                print("\nCouldn't automatically extract participants.")
                print("Please enter email addresses manually.\n")
                
                emails = [config.EMAIL_HOST_USER]  # Always include the default
                
                while True:
                    email = input("Enter participant email (or press Enter to finish): ").strip()
                    if not email:
                        break
                    if "@" in email:
                        emails.append(email)
                        print(f"Added {email} to recipients list")
                    else:
                        print("Invalid email format. Please include @ symbol.")
            
            # Always include default email if not already in list
            if config.EMAIL_HOST_USER not in emails:
                emails.append(config.EMAIL_HOST_USER)
            
            # Remove duplicates while preserving order
            self.participants = list(dict.fromkeys(emails))
            
            print(f"\nWill send transcript to {len(self.participants)} recipient(s):")
            for email in self.participants:
                print(f"- {email}")
                
        except Exception as e:
            print(f"Error collecting participants: {e}")
            # Fallback to default email
            self.participants = [config.EMAIL_HOST_USER]
            print(f"Using fallback email: {config.EMAIL_HOST_USER}")
            
    def leave_meeting(self):
        """Leave the Google Meet."""
        try:
            leave_button = self.driver.find_element(By.XPATH, "//div[@aria-label='Leave call']")
            leave_button.click()
        except:
            print("Could not find leave button, closing browser instead")
            
        # Close the browser
        self.driver.quit()
        
    def run_meeting_bot(self, meet_url, duration_minutes=60):
        """Run the entire meeting bot workflow with better error recovery."""
        transcript = "No transcript available"  # Default value
        summary = "No summary available"  # Default value
        
        try:
            self.setup_driver()
            
            # Try login but continue even if it fails
            try:
                self.login_to_google()
            except Exception as login_e:
                print(f"Login failed but continuing: {login_e}")
            
            # Try joining but continue if it fails
            try:
                self.join_meeting(meet_url)
            except Exception as join_e:
                print(f"Join failed but continuing: {join_e}")
            
            # Add to your run_meeting_bot method in meetbot.py
            # After joining the meeting but before recording:

            print("\n" + "=" * 60)
            print("🎙️ AUDIO PERMISSION REQUIRED 🎙️")
            print("=" * 60)
            print("1. A dialog box will appear asking what you want to share")
            print("2. Select 'Chrome Tab' (NOT your entire screen)")
            print("3. Choose the tab with Google Meet")
            print("4. IMPORTANT: Check the 'Share audio' checkbox at the bottom")
            print("5. Click 'Share' button")
            print("=" * 60 + "\n")

            # Wait for user to be ready
            time.sleep(3)
            print("Starting audio capture in 5 seconds...")
            time.sleep(5)

            # Always generate a transcript (real or mock)
            transcript = record_and_transcribe(duration_minutes * 60, self.driver)
            print(f"Transcript obtained: {len(transcript)} characters")

            # For testing: Skip summary generation and just use the transcript
            if transcript and len(transcript) > 10:
                print("\nRAW TRANSCRIPT FROM AUDIO:")
                print("=" * 60)
                print(transcript)
                print("=" * 60)
                summary = "TESTING MODE: Raw transcript: " + transcript
            else:
                print("No usable transcript was generated from the audio.")
                summary = "No usable transcript was obtained from the audio."

            # Collect participant emails before sending
            try:
                self.collect_participants()
            except Exception as participant_error:
                print(f"Error collecting participants: {participant_error}")
                self.participants = [config.EMAIL_HOST_USER]

            # Always send email with RAW transcript to all participants
            print(f"Sending transcript to {len(self.participants)} recipients...")
            send_summary_emails(self.participants, 
                              f"RAW TRANSCRIPT: {transcript}", 
                              meet_url)
                
            return transcript  # Return transcript instead of summary
            
        except Exception as e:
            print(f"Error in meeting bot: {e}")
            # Always try to close browser and send email
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                    
            # Send whatever we have
            send_summary_emails([config.EMAIL_HOST_USER], 
                              f"Error in bot, but transcript was: {transcript}", 
                              meet_url)
            
            return "Error occurred during the meeting bot workflow."
                
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Google Meet Bot')
    parser.add_argument('--url', type=str, required=True, help='Google Meet URL')
    parser.add_argument('--duration', type=int, default=60, help='Meeting duration in minutes')
    
    args = parser.parse_args()
    
    print(f"Starting bot with URL: {args.url} and duration: {args.duration} minutes")
    
    bot = GoogleMeetBot()
    try:
        transcript = bot.run_meeting_bot(args.url, args.duration)
        print("\nRaw Transcript:")
        print("=" * 60)
        print(transcript)
        print("=" * 60)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
