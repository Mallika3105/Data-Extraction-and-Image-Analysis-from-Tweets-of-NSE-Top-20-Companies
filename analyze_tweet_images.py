#!/usr/bin/env python3
"""
Analyze Tweet Images

This script analyzes images from tweets to:
1. Count the number of images per tweet
2. Detect if humans are present in the images using OpenCV's face detection
3. Estimate gender based on a simple heuristic
4. Create a new CSV with the enhanced dataset

Requirements:
- pip install opencv-python
- pip install pandas
"""

import os
import csv
import cv2
import pandas as pd
import glob
from datetime import datetime
import numpy as np
import requests
from urllib.parse import urlparse

# Input file (merged CSV)
INPUT_FILE = "all_company_tweets_20250517_155120.csv"  # Update with your actual filename
# Output file for enhanced dataset
OUTPUT_FILE = f"enhanced_tweets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
# Base directory for company tweets
BASE_DIR = "company_tweets"
# Temporary directory for downloading images that aren't already local
TEMP_DIR = "temp_images"

# Create temp directory if it doesn't exist
os.makedirs(TEMP_DIR, exist_ok=True)

def download_image(url, output_path):
    """Download an image from a URL to a local path."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return output_path
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
        return None

def get_image_paths(tweet_row):
    """Get local paths for all images in a tweet."""
    image_paths = []

    # Check if there are local images already downloaded
    if tweet_row['Local_Images'] and tweet_row['Local_Images'] != '':
        # Split by semicolon to get individual paths
        paths = tweet_row['Local_Images'].split('; ')
        for path in paths:
            if os.path.exists(path):
                image_paths.append(path)
            else:
                print(f"Warning: Local image {path} not found")

    # If no valid local images, try downloading from URLs
    if not image_paths and tweet_row['Image_URLs'] and tweet_row['Image_URLs'] != '':
        urls = tweet_row['Image_URLs'].split('; ')
        for i, url in enumerate(urls):
            # Create a filename based on tweet ID and image number
            filename = f"{tweet_row['Tweet_ID']}_img_{i+1}.jpg"
            output_path = os.path.join(TEMP_DIR, filename)

            # Download the image
            downloaded_path = download_image(url, output_path)
            if downloaded_path:
                image_paths.append(downloaded_path)

    return image_paths

def analyze_image(image_path):
    """
    Analyze an image to detect humans using OpenCV's face detection.
    Returns a tuple of (human_present, gender)
    """
    try:
        # Read the image
        img = cv2.imread(image_path)
        if img is None:
            print(f"Warning: Could not read image {image_path}")
            return False, "unknown"

        # Load pre-trained face detector
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

        # Convert to grayscale for face detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Detect faces
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)

        # If no faces detected
        if len(faces) == 0:
            return False, "unknown"

        # Faces detected - for simplicity, we'll use a basic heuristic for gender
        # In a real application, you would use a proper gender classification model
        # This is just a placeholder that randomly assigns gender
        if len(faces) == 1:
            # For demonstration, we'll use a simple heuristic
            # In a real application, you would use a proper gender classifier
            face_width = faces[0][2]
            face_height = faces[0][3]

            # Simple heuristic: if face is wider than tall, classify as male (very simplified)
            if face_width > face_height:
                return True, "male"
            else:
                return True, "female"
        else:
            # Multiple faces detected
            return True, "both"

    except Exception as e:
        # Error in processing
        print(f"Error analyzing image {image_path}: {e}")
        return False, "unknown"

def process_tweet(tweet_row):
    """Process a tweet to analyze its images."""
    # Get image paths
    image_paths = get_image_paths(tweet_row)
    num_images = len(image_paths)

    # Initialize variables
    human_present = "no"
    detected_gender = "unknown"

    # If there are images, analyze them
    if num_images > 0:
        # Analyze each image
        humans_detected = False
        genders = []

        for image_path in image_paths:
            human, gender = analyze_image(image_path)
            if human:
                humans_detected = True
                genders.append(gender)

        # Update human_present flag
        if humans_detected:
            human_present = "yes"

        # Determine overall gender
        if "both" in genders:
            detected_gender = "both"
        elif "male" in genders and "female" in genders:
            detected_gender = "both"
        elif "male" in genders:
            detected_gender = "male"
        elif "female" in genders:
            detected_gender = "female"

    # Construct tweet URL
    tweet_url = f"https://twitter.com/{tweet_row['Company_Handle']}/status/{tweet_row['Tweet_ID']}"

    # Create result row
    result = {
        'tweet_url': tweet_url,
        'text': tweet_row['Tweet_Text'],
        'likes_count': tweet_row['Likes'],
        'reshares_count': tweet_row['Retweets'],
        'num_images': num_images,
        'human_present': human_present,
        'detected_gender': detected_gender,
        'image_file_paths': '; '.join(image_paths) if image_paths else '',
        'company_name': tweet_row['Company_Name'],
        'company_handle': tweet_row['Company_Handle'],
        'tweet_id': tweet_row['Tweet_ID'],
        'date': tweet_row['Date']
    }

    return result

def main():
    """Main function to process all tweets."""
    print(f"Reading input file: {INPUT_FILE}")

    # Read the input CSV file
    df = pd.read_csv(INPUT_FILE)
    total_tweets = len(df)
    print(f"Found {total_tweets} tweets to process")

    # Filter to only include tweets with images
    tweets_with_images = df[(df['Image_URLs'].notna()) & (df['Image_URLs'] != '')]
    print(f"Found {len(tweets_with_images)} tweets with images")

    # Process all tweets with images
    print(f"Processing all {len(tweets_with_images)} tweets with images")

    # Process tweets with images
    results = []

    print("Processing tweets with images...")

    # Process each tweet with images
    for i, (_, row) in enumerate(tweets_with_images.iterrows(), 1):
        try:
            if i % 10 == 0 or i == 1 or i == len(tweets_with_images):
                print(f"Processing tweet {i}/{len(tweets_with_images)} from {row['Company_Name']}...")

            result = process_tweet(row)
            results.append(result)

            # Print progress for every 10th tweet
            if i % 10 == 0 or i == 1 or i == len(tweets_with_images):
                print(f"  - Found {result['num_images']} images, humans: {result['human_present']}, gender: {result['detected_gender']}")

        except Exception as e:
            print(f"Error processing tweet: {e}")

    # Process a sample of tweets without images (for efficiency)
    print("Processing tweets without images...")
    tweets_without_images = df[~df.index.isin(tweets_with_images.index)]
    sample_size_no_img = min(100, len(tweets_without_images))
    tweets_without_images_sample = tweets_without_images.sample(sample_size_no_img, random_state=42)

    for i, (_, row) in enumerate(tweets_without_images_sample.iterrows(), 1):
        if i % 10 == 0:
            print(f"Processing tweet without images {i}/{sample_size_no_img}...")

        # Construct tweet URL
        tweet_url = f"https://twitter.com/{row['Company_Handle']}/status/{row['Tweet_ID']}"

        # Create result row
        result = {
            'tweet_url': tweet_url,
            'text': row['Tweet_Text'],
            'likes_count': row['Likes'],
            'reshares_count': row['Retweets'],
            'num_images': 0,
            'human_present': "no",
            'detected_gender': "unknown",
            'image_file_paths': '',
            'company_name': row['Company_Name'],
            'company_handle': row['Company_Handle'],
            'tweet_id': row['Tweet_ID'],
            'date': row['Date']
        }

        results.append(result)

    # Convert results to DataFrame
    results_df = pd.DataFrame(results)

    # Sort by date (newest first)
    results_df = results_df.sort_values('date', ascending=False)

    # Write to CSV
    results_df.to_csv(OUTPUT_FILE, index=False)

    print(f"\nEnhanced dataset saved to {OUTPUT_FILE}")
    print(f"Total tweets processed: {len(results_df)}")
    print(f"Tweets with images: {len(tweets_with_images)}")
    print(f"Tweets with humans detected: {len(results_df[results_df['human_present'] == 'yes'])}")

    print("\nExample of the final dataset structure:")
    print(results_df[['tweet_url', 'text', 'likes_count', 'reshares_count', 'num_images', 'human_present', 'detected_gender']].head(3))

if __name__ == "__main__":
    main()
