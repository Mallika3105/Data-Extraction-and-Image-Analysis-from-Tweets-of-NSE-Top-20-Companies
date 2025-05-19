#!/usr/bin/env python3
"""
Twitter Scraper for using Selenium

This script uses Selenium to automate a web browser and scrape tweets from
the Twitter handle. It simulates a real user browsing Twitter,
which helps bypass some anti-scraping measures.

The data is saved to a CSV file.
"""

import csv
import time
import random
from datetime import datetime
import re
import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# List of companies and their Twitter handles to scrape
COMPANIES = [
    {"name": "Reliance Industries Ltd", "handle": "RIL_Updates"},
    {"name": "HDFC Bank Ltd", "handle": "HDFC_Bank"},
    {"name": "Tata Consultancy Services Ltd", "handle": "TCS"},
    {"name": "Bharti Airtel Ltd", "handle": "airtelnews"},
    {"name": "ICICI Bank Ltd", "handle": "ICICIBank"},
    {"name": "State Bank of India", "handle": "TheOfficialSBI"},
    {"name": "Infosys Ltd", "handle": "Infosys"},
    {"name": "Bajaj Finance Ltd", "handle": "Bajaj_Finance"},
    {"name": "Hindustan Unilever Ltd", "handle": "HUL_News"},
    {"name": "ITC Ltd", "handle": "ITCCorpCom"},
    {"name": "Larsen & Toubro Ltd", "handle": "larsentoubro"},
    {"name": "HCL Technologies Ltd", "handle": "hcltech"},
    {"name": "Kotak Mahindra Bank Ltd", "handle": "KotakBankLtd"},
    {"name": "Sun Pharmaceutical Industries Ltd", "handle": "SunPharma_Live"},
    {"name": "Maruti Suzuki India Ltd", "handle": "Maruti_Corp"},
    {"name": "Mahindra & Mahindra Ltd", "handle": "MahindraRise"},
    {"name": "Axis Bank Ltd", "handle": "AxisBank"},
    {"name": "UltraTech Cement Ltd", "handle": "UltraTechCement"},
    {"name": "NTPC Ltd", "handle": "ntpclimited"},
    {"name": "Bajaj Finserv Ltd", "handle": "Bajaj_Finserv"}
]

# Number of tweets to fetch per company (approximate)
TWEET_LIMIT = 100
# Twitter login URL
TWITTER_LOGIN_URL = "https://twitter.com/i/flow/login"
# Scroll pause time
SCROLL_PAUSE_TIME = 2
# Base directory for saving data
BASE_DIR = "company_tweets"
# Twitter credentials will be prompted at runtime if needed


def setup_driver():
    """Set up and return a configured Chrome WebDriver."""
    print("Setting up Chrome WebDriver...")

    # Configure Chrome options
    chrome_options = Options()
    # Note: We're not using headless mode to better simulate a real user
    # chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Hide automation
    chrome_options.add_argument("--lang=en-US,en;q=0.9")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # Add experimental options
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # Set up the driver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Execute CDP commands to hide automation
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return driver


def scrape_tweets(driver, twitter_handle):
    """Scrape tweets from the specified Twitter handle."""
    print(f"Scraping tweets from @{twitter_handle}...")

    # Navigate to the Twitter profile
    twitter_url = f"https://twitter.com/{twitter_handle}/tweets"
    driver.get(twitter_url)

    # Wait for the page to load
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
        )
    except TimeoutException:
        print("Timed out waiting for page to load")
        return []

    # Scroll down to load more tweets
    tweets_data = []
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_attempts = 0
    max_scroll_attempts = 30  # Increase this to allow more scrolling
    no_new_tweets_count = 0

    while len(tweets_data) < TWEET_LIMIT and scroll_attempts < max_scroll_attempts:
        scroll_attempts += 1

        # Scroll down
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # Wait for new tweets to load with a longer pause
        time.sleep(SCROLL_PAUSE_TIME * 1.5)

        # Extract tweets
        articles = driver.find_elements(By.CSS_SELECTOR, "article")

        tweets_before = len(tweets_data)

        for article in articles:
            try:
                if article.get_attribute("data-testid") == "tweet":
                    tweet = extract_tweet_data(article)
                    if tweet and tweet["id"] not in [t["id"] for t in tweets_data]:
                        tweets_data.append(tweet)
                        print(f"Found tweet: {tweet['id']}")
            except Exception as e:
                print(f"Error processing article: {e}")
                continue

        # Check if we found new tweets in this iteration
        if len(tweets_data) == tweets_before:
            no_new_tweets_count += 1
            if no_new_tweets_count >= 3:  # If no new tweets for 3 consecutive scrolls
                # Try clicking "Show more tweets" button if it exists
                try:
                    show_more_button = driver.find_element(By.XPATH, "//span[contains(text(), 'Show more')]")
                    driver.execute_script("arguments[0].click();", show_more_button)
                    print("Clicked 'Show more tweets' button")
                    time.sleep(SCROLL_PAUSE_TIME * 2)
                    no_new_tweets_count = 0  # Reset counter after clicking
                except NoSuchElementException:
                    # If we can't find more tweets after multiple attempts, we might be at the end
                    if no_new_tweets_count >= 5:
                        print("No new tweets found after multiple scroll attempts")
                        break
        else:
            no_new_tweets_count = 0  # Reset counter when we find new tweets

        # Check if we've reached the end of the page
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            # Try one more time with a longer wait
            time.sleep(SCROLL_PAUSE_TIME * 2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                # Try to force load more by scrolling up and down
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.8);")
                time.sleep(SCROLL_PAUSE_TIME)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(SCROLL_PAUSE_TIME)

                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    print("Reached the end of the timeline or Twitter is not loading more tweets")
                    break

        last_height = new_height

        # Print progress
        print(f"Collected {len(tweets_data)} tweets so far... (Scroll attempt {scroll_attempts}/{max_scroll_attempts})")

        # Add a random delay to avoid detection
        time.sleep(random.uniform(1.5, 4.0))

    print(f"Found {len(tweets_data)} tweets for @{twitter_handle}.")
    return tweets_data


def extract_tweet_data(article):
    """Extract data from a tweet article element."""
    try:
        # Extract tweet ID from the permalink
        try:
            permalink = article.find_element(By.CSS_SELECTOR, "a[href*='/status/']").get_attribute("href")
            tweet_id = re.search(r"/status/(\d+)", permalink).group(1)
        except (NoSuchElementException, AttributeError) as e:
            print(f"Could not extract tweet ID: {e}")
            return None

        # Extract tweet text
        try:
            text_element = article.find_element(By.CSS_SELECTOR, "[data-testid='tweetText']")
            text = text_element.text
        except NoSuchElementException:
            # Some tweets might not have text (e.g., only media)
            text = ""

        # Extract timestamp
        try:
            time_element = article.find_element(By.CSS_SELECTOR, "time")
            timestamp = time_element.get_attribute("datetime")
        except NoSuchElementException:
            timestamp = ""

        # Extract engagement metrics
        metrics = {"replies": 0, "retweets": 0, "likes": 0}
        try:
            # Try different selectors for metrics
            for metric, selector_list in {
                "reply": ["[data-testid='reply']", "[aria-label*='repl']"],
                "retweet": ["[data-testid='retweet']", "[aria-label*='retweet']"],
                "like": ["[data-testid='like']", "[aria-label*='like']"]
            }.items():
                for selector in selector_list:
                    try:
                        metric_elements = article.find_elements(By.CSS_SELECTOR, selector)
                        for metric_element in metric_elements:
                            try:
                                # Try to find the count in different ways
                                count_text = ""

                                # Method 1: Direct span
                                try:
                                    count_element = metric_element.find_element(By.CSS_SELECTOR, "span[data-testid='app-text-transition-container']")
                                    count_text = count_element.text
                                except NoSuchElementException:
                                    pass

                                # Method 2: Aria label
                                if not count_text and metric_element.get_attribute("aria-label"):
                                    aria_label = metric_element.get_attribute("aria-label")
                                    count_match = re.search(r'(\d+(?:\.\d+)?[KMB]?)', aria_label)
                                    if count_match:
                                        count_text = count_match.group(1)

                                # Convert the count text to a number
                                if count_text:
                                    if 'K' in count_text:
                                        count = float(count_text.replace('K', '')) * 1000
                                    elif 'M' in count_text:
                                        count = float(count_text.replace('M', '')) * 1000000
                                    elif 'B' in count_text:
                                        count = float(count_text.replace('B', '')) * 1000000000
                                    else:
                                        count = int(count_text) if count_text.isdigit() else 0

                                    metrics[f"{metric}s"] = count
                                    break  # Found the count, no need to try other elements
                            except Exception as e:
                                continue  # Try the next element

                        if metrics[f"{metric}s"] > 0:
                            break  # Found the metric, no need to try other selectors
                    except Exception:
                        continue  # Try the next selector
        except Exception as e:
            print(f"Error extracting metrics: {e}")

        # Extract media (photos)
        photos = []
        try:
            # Try different selectors for media
            for selector in [
                "img[src*='https://pbs.twimg.com/media/']",
                "img[src*='pbs.twimg.com/media']",
                "div[data-testid='tweetPhoto'] img"
            ]:
                media_elements = article.find_elements(By.CSS_SELECTOR, selector)
                for img in media_elements:
                    src = img.get_attribute("src")
                    if src and src not in photos and "profile" not in src.lower() and "avatar" not in src.lower():
                        photos.append(src)

            # If we found no photos, try looking for video thumbnails
            if not photos:
                video_elements = article.find_elements(By.CSS_SELECTOR, "div[data-testid='videoPlayer'] img")
                for img in video_elements:
                    src = img.get_attribute("src")
                    if src and src not in photos:
                        photos.append(src)
        except Exception as e:
            print(f"Error extracting photos: {e}")

        return {
            "id": tweet_id,
            "url": permalink,
            "text": text,
            "timestamp": timestamp,
            "replies": metrics.get("replies", 0),
            "retweets": metrics.get("retweets", 0),
            "likes": metrics.get("likes", 0),
            "photos": photos
        }

    except Exception as e:
        print(f"Error extracting tweet data: {e}")
        return None


def download_image(url, folder, filename):
    """Download an image from a URL and save it to a folder."""
    import requests
    from urllib.parse import urlparse

    # Create the folder if it doesn't exist
    os.makedirs(folder, exist_ok=True)

    try:
        # Get the image extension from the URL
        parsed_url = urlparse(url)
        path = parsed_url.path
        ext = os.path.splitext(path)[1]
        if not ext:
            ext = '.jpg'  # Default extension

        # Full path to save the image
        filepath = os.path.join(folder, f"{filename}{ext}")

        # Download the image
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return filepath
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
        return None


def save_to_csv(tweets, twitter_handle):
    """Save tweets to a CSV file with a more structured format."""
    if not tweets:
        print(f"No tweets to save for @{twitter_handle}.")
        return

    # Create base directory if it doesn't exist
    os.makedirs(BASE_DIR, exist_ok=True)

    # Create a folder for images
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    image_folder = os.path.join(BASE_DIR, f"{twitter_handle}_images_{timestamp}")

    # Output file path
    output_file = os.path.join(BASE_DIR, f"{twitter_handle}_tweets_{timestamp}.csv")

    fieldnames = [
        'S.No',
        'Tweet_ID',
        'Date',
        'Tweet_Text',
        'Likes',
        'Retweets',
        'Replies',
        'Image_URLs',
        'Local_Images'
    ]

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for i, tweet in enumerate(tweets, 1):
            # Download images if present
            local_images = []
            if tweet['photos']:
                for j, photo_url in enumerate(tweet['photos'], 1):
                    local_path = download_image(
                        photo_url,
                        image_folder,
                        f"tweet_{tweet['id']}_img_{j}"
                    )
                    if local_path:
                        local_images.append(local_path)

            # Format the date
            date = tweet['timestamp']
            try:
                # Convert ISO format to more readable format
                date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
                formatted_date = date_obj.strftime('%Y-%m-%d %H:%M:%S')
            except:
                formatted_date = date

            writer.writerow({
                'S.No': i,
                'Tweet_ID': tweet['id'],
                'Date': formatted_date,
                'Tweet_Text': tweet['text'],
                'Likes': tweet['likes'],
                'Retweets': tweet['retweets'],
                'Replies': tweet['replies'],
                'Image_URLs': '; '.join(tweet['photos']) if tweet['photos'] else '',
                'Local_Images': '; '.join(local_images) if local_images else ''
            })

    print(f"Tweets saved to {output_file}")
    if os.path.exists(image_folder) and os.listdir(image_folder):
        print(f"Images saved to {image_folder}/")

    return output_file


def login_to_twitter(driver):
    """Log in to Twitter with credentials provided at runtime."""
    import getpass

    print("Twitter login is recommended to access more tweets.")
    print("Would you like to log in to Twitter? (y/n)")
    choice = input().strip().lower()

    if choice != 'y':
        print("Proceeding without login.")
        return False

    # Prompt for credentials
    username = input("Enter your Twitter username or email: ").strip()
    password = getpass.getpass("Enter your Twitter password: ")

    if not username or not password:
        print("No Twitter credentials provided. Proceeding without login.")
        return False

    print("Logging in to Twitter...")

    try:
        # Navigate to the login page
        driver.get(TWITTER_LOGIN_URL)

        # Wait for the login page to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='text']"))
        )

        # Enter username/email
        username_field = driver.find_element(By.CSS_SELECTOR, "input[name='text']")
        username_field.send_keys(username)

        # Click the Next button
        next_button = driver.find_element(By.XPATH, "//span[contains(text(), 'Next')]")
        next_button.click()

        # Wait for password field
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='password']"))
        )

        # Enter password
        password_field = driver.find_element(By.CSS_SELECTOR, "input[name='password']")
        password_field.send_keys(password)

        # Click the Log in button
        login_button = driver.find_element(By.XPATH, "//span[contains(text(), 'Log in')]")
        login_button.click()

        # Wait for the home page to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[aria-label='Home']"))
        )

        print("Successfully logged in to Twitter")
        return True

    except Exception as e:
        print(f"Error logging in to Twitter: {e}")
        return False


def main():
    """Main function."""
    # Create a summary CSV file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    summary_file = os.path.join(BASE_DIR, f"company_tweets_summary_{timestamp}.csv")
    os.makedirs(BASE_DIR, exist_ok=True)

    with open(summary_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Company Name', 'Twitter Handle', 'Tweets CSV File', 'Tweet Count', 'Images Count'])

    # Process companies one by one with separate browser sessions
    for company in COMPANIES:
        company_name = company['name']
        twitter_handle = company['handle']

        print(f"\n{'='*80}")
        print(f"Processing {company_name} (@{twitter_handle})")
        print(f"{'='*80}\n")

        # Set up a new driver for each company to avoid session issues
        driver = None

        try:
            # Create a fresh browser instance
            driver = setup_driver()

            # Try to log in to Twitter
            login_to_twitter(driver)

            # Scrape tweets
            tweets = scrape_tweets(driver, twitter_handle)

            # Save to CSV
            if tweets:
                output_file = save_to_csv(tweets, twitter_handle)

                # Count images
                image_count = sum(1 for tweet in tweets if tweet['photos'])

                # Update summary
                with open(summary_file, 'a', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow([
                        company_name,
                        twitter_handle,
                        output_file,
                        len(tweets),
                        image_count
                    ])
            else:
                print(f"No tweets found for {company_name} (@{twitter_handle})")

                # Update summary with empty results
                with open(summary_file, 'a', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow([company_name, twitter_handle, "No tweets found", 0, 0])

        except Exception as e:
            print(f"Error processing {company_name} (@{twitter_handle}): {e}")

            # Update summary with error
            with open(summary_file, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([company_name, twitter_handle, f"Error: {str(e)}", 0, 0])

        finally:
            # Clean up the driver
            if driver:
                try:
                    driver.quit()
                except:
                    pass

        # Add a delay between companies to avoid rate limiting
        delay = random.uniform(5.0, 10.0)
        print(f"Waiting {delay:.2f} seconds before processing the next company...")
        time.sleep(delay)

    print(f"\nSummary saved to {summary_file}")


if __name__ == "__main__":
    main()
