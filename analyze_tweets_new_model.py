#!/usr/bin/env python3
"""
Analyze Tweet Images with Enhanced Human Detection

This script analyzes images from tweets to:
1. Count the number of images per tweet
2. Detect if humans are present using YOLOv8
3. Estimate gender using DeepFace
4. Save results to a new CSV file

Requirements:
- pip install opencv-python pandas ultralytics deepface
"""

import os
import cv2
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from ultralytics import YOLO
from deepface import DeepFace

# Input/output config
INPUT_FILE = "all_company_tweets_20250517_155120.csv"
OUTPUT_FILE = f"Test_enhanced_tweets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
TEMP_DIR = "temp_images"
os.makedirs(TEMP_DIR, exist_ok=True)

# Load YOLO model for human detection
yolo_model = YOLO("yolov8n.pt")  # you can use 'yolov8s.pt' or larger if needed

def download_image(url, output_path):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)
        return output_path
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
        return None

def get_image_paths(tweet_row):
    image_paths = []

    if tweet_row.get('Local_Images') and tweet_row['Local_Images'] != '':
        paths = tweet_row['Local_Images'].split('; ')
        for path in paths:
            if os.path.exists(path):
                image_paths.append(path)
            else:
                print(f"Warning: Local image {path} not found")

    if not image_paths and tweet_row.get('Image_URLs') and tweet_row['Image_URLs'] != '':
        urls = tweet_row['Image_URLs'].split('; ')
        for i, url in enumerate(urls):
            filename = f"{tweet_row['Tweet_ID']}_img_{i+1}.jpg"
            output_path = os.path.join(TEMP_DIR, filename)
            downloaded_path = download_image(url, output_path)
            if downloaded_path:
                image_paths.append(downloaded_path)

    return image_paths

def analyze_image(image_path):
    """
    Analyze image using YOLOv8 for human detection and DeepFace for gender.
    Returns (human_present, gender)
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            print(f"Warning: Could not read image {image_path}")
            return False, "unknown"

        results = yolo_model(img)
        human_detected = False
        genders = []

        for result in results:
            for box in result.boxes.data:
                cls = int(box[5])
                if cls == 0:  # class 0 = person
                    human_detected = True
                    x1, y1, x2, y2 = map(int, box[:4])
                    face_img = img[y1:y2, x1:x2]

                    try:
                        analysis = DeepFace.analyze(face_img, actions=['gender'], enforce_detection=False)
                        gender_scores = analysis[0]['gender']
                        if isinstance(gender_scores, dict):
                            predicted_gender = max(gender_scores, key=gender_scores.get).lower()
                            if predicted_gender in ['man', 'male']:
                                genders.append("male")
                            elif predicted_gender in ['woman', 'female']:
                                genders.append("female")
                            else:
                                genders.append("unknown")
                        else:
                            genders.append("unknown")
                    except Exception as e:
                        print(f"DeepFace error: {e}")
                        genders.append("unknown")

        if not human_detected:
            return False, "unknown"

        if "male" in genders and "female" in genders:
            return True, "both"
        elif "male" in genders:
            return True, "male"
        elif "female" in genders:
            return True, "female"
        else:
            return True, "unknown"

    except Exception as e:
        print(f"Error analyzing image {image_path}: {e}")
        return False, "unknown"

def process_tweet(tweet_row):
    image_paths = get_image_paths(tweet_row)
    num_images = len(image_paths)

    human_present = "no"
    detected_gender = "unknown"

    if num_images > 0:
        humans_detected = False
        genders = []

        for image_path in image_paths:
            human, gender = analyze_image(image_path)
            if human:
                humans_detected = True
                genders.append(gender)

        if humans_detected:
            human_present = "yes"

        if "both" in genders:
            detected_gender = "both"
        elif "male" in genders and "female" in genders:
            detected_gender = "both"
        elif "male" in genders:
            detected_gender = "male"
        elif "female" in genders:
            detected_gender = "female"

    tweet_url = f"https://twitter.com/{tweet_row['Company_Handle']}/status/{tweet_row['Tweet_ID']}"
    return {
        'tweet_url': tweet_url,
        'text': tweet_row['Tweet_Text'],
        'likes_count': tweet_row['Likes'],
        'reshares_count': tweet_row['Retweets'],
        'num_images': num_images,
        'human_present': human_present,
        'detected_gender': detected_gender,
        'image_file_paths': '; '.join(image_paths),
        'company_name': tweet_row['Company_Name'],
        'company_handle': tweet_row['Company_Handle'],
        'tweet_id': tweet_row['Tweet_ID'],
        'date': tweet_row['Date']
    }

def main():
    print(f"Reading input file: {INPUT_FILE}")
    df = pd.read_csv(INPUT_FILE)
    print(f"Found {len(df)} total tweets")

    tweets_with_images = df[(df['Image_URLs'].notna()) & (df['Image_URLs'] != '')]
    print(f"Found {len(tweets_with_images)} tweets with images")

    results = []

    for i, (_, row) in enumerate(tweets_with_images.iterrows(), 1):
        try:
            if i % 10 == 0 or i == 1 or i == len(tweets_with_images):
                print(f"Processing tweet {i}/{len(tweets_with_images)} from {row['Company_Name']}...")
            result = process_tweet(row)
            results.append(result)
        except Exception as e:
            print(f"Error processing tweet: {e}")

    print("Processing a sample of tweets without images...")
    tweets_without_images = df[~df.index.isin(tweets_with_images.index)]
    sample_size_no_img = min(100, len(tweets_without_images))
    tweets_without_images_sample = tweets_without_images.sample(sample_size_no_img, random_state=42)

    for i, (_, row) in enumerate(tweets_without_images_sample.iterrows(), 1):
        tweet_url = f"https://twitter.com/{row['Company_Handle']}/status/{row['Tweet_ID']}"
        results.append({
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
        })

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('date', ascending=False)
    results_df.to_csv(OUTPUT_FILE, index=False)

    print(f"\n✅ Enhanced dataset saved to {OUTPUT_FILE}")
    print(f"Total tweets processed: {len(results_df)}")
    print(f"Tweets with humans detected: {len(results_df[results_df['human_present'] == 'yes'])}")
    print("\nSample output:")
    print(results_df[['tweet_url', 'text', 'likes_count', 'reshares_count', 'num_images', 'human_present', 'detected_gender']].head(3))

if __name__ == "__main__":
    main()
