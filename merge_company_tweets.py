#!/usr/bin/env python3
"""
Merge Company Tweets

This script merges all individual company tweet CSV files into one consolidated CSV file.
It adds a 'Company' column to identify which company each tweet belongs to.
"""

import os
import csv
import glob
from datetime import datetime

# Base directory where company tweets are stored
BASE_DIR = "company_tweets"
# Output file for merged tweets
OUTPUT_FILE = f"all_company_tweets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

def merge_csv_files():
    """Merge all company tweet CSV files into one consolidated file."""
    # Find all CSV files in the company_tweets directory that contain tweet data
    csv_files = glob.glob(os.path.join(BASE_DIR, "*_tweets_*.csv"))

    # Filter out summary files
    csv_files = [f for f in csv_files if "summary" not in f.lower()]

    if not csv_files:
        print("No CSV files found to merge.")
        return

    print(f"Found {len(csv_files)} CSV files to merge.")

    # Create a list to store all tweets
    all_tweets = []

    # Process each CSV file
    for csv_file in csv_files:
        # Extract company handle from filename
        filename = os.path.basename(csv_file)
        company_handle = filename.split('_tweets_')[0]

        # Find the corresponding company name from the summary file
        company_name = get_company_name(company_handle)

        print(f"Processing {company_name} (@{company_handle})...")

        try:
            # Read the CSV file
            with open(csv_file, 'r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)

                # Check if this is a tweet file (should have Tweet_ID or similar column)
                fieldnames = reader.fieldnames
                if not fieldnames or not any(field in fieldnames for field in ['Tweet_ID', 'tweet_id', 'Tweet ID']):
                    print(f"  Skipping {csv_file} - not a tweet file")
                    continue

                # Add each tweet to the list with company information
                for row in reader:
                    # Create a standardized tweet dictionary
                    tweet = {
                        'Company_Name': company_name,
                        'Company_Handle': company_handle,
                        'S.No': row.get('S.No', ''),
                        'Tweet_ID': row.get('Tweet_ID', row.get('tweet_id', '')),
                        'Date': row.get('Date', row.get('timestamp', '')),
                        'Tweet_Text': row.get('Tweet_Text', row.get('text', '')),
                        'Likes': row.get('Likes', row.get('likes', '0')),
                        'Retweets': row.get('Retweets', row.get('retweets', '0')),
                        'Replies': row.get('Replies', row.get('replies', '0')),
                        'Image_URLs': row.get('Image_URLs', row.get('photos', '')),
                        'Local_Images': row.get('Local_Images', '')
                    }

                    # Add to the list
                    all_tweets.append(tweet)
        except Exception as e:
            print(f"  Error processing {csv_file}: {e}")

    # Sort tweets by date (newest first)
    all_tweets.sort(key=lambda x: x.get('Date', ''), reverse=True)

    # Define the fieldnames for the output CSV
    fieldnames = [
        'Company_Name',
        'Company_Handle',
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

    # Write the merged data to the output file
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        # Add a new serial number for the consolidated file
        for i, tweet in enumerate(all_tweets, 1):
            tweet['S.No'] = i
            writer.writerow(tweet)

    print(f"Merged {len(all_tweets)} tweets from {len(csv_files)} companies into {OUTPUT_FILE}")


def get_company_name(company_handle):
    """Get the company name for a given handle from the summary file."""
    # Find the most recent summary file
    summary_files = glob.glob(os.path.join(BASE_DIR, "company_tweets_summary_*.csv"))

    if not summary_files:
        # If no summary file is found, return the handle as the name
        return company_handle

    # Get the most recent summary file
    summary_file = max(summary_files)

    # Read the summary file to find the company name
    with open(summary_file, 'r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header

        for row in reader:
            if len(row) >= 2 and row[1] == company_handle:
                return row[0]

    # If company name not found, return the handle
    return company_handle


if __name__ == "__main__":
    merge_csv_files()
