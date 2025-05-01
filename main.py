from twikit import Client, TooManyRequests
import time
from datetime import datetime
import csv
from configparser import ConfigParser
from random import randint
import asyncio
import os
import re
import aiohttp
import urllib.parse

MINIMUM_TWEETS = 20
QUERY = '(#Covid) lang:en until:2025-01-01 since:2024-01-01 -filter:retweets -filter:replies'
IMAGES_DIR = 'downloaded_images'
PROFILE_PICS_DIR = 'profile_pics'

# Create directories if they don't exist
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(PROFILE_PICS_DIR, exist_ok=True)

# Async function to download an image
async def download_image(session, url, filepath):
    try:
        print(f"{datetime.now()} - Attempting to download image from: {url}")
        async with session.get(url) as response:
            if response.status == 200:
                content = await response.read()
                if len(content) > 0:  # Check if we actually got content
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    print(f"{datetime.now()} - Successfully downloaded image to {filepath}")
                    return filepath
                else:
                    print(f"{datetime.now()} - Download returned empty content: {url}")
                    return None
            else:
                print(f"{datetime.now()} - Failed to download image: {url}, status: {response.status}")
                return None
    except Exception as e:
        print(f"{datetime.now()} - Error downloading image {url}: {e}")
        return None

# Extract t.co links from tweet text
def extract_links(text):
    # Pattern to match t.co URLs
    pattern = r'https?://t\.co/\w+'
    return re.findall(pattern, text)

# Function to print tweet structure for debugging
def print_tweet_structure(tweet, level=0, max_level=3):
    """Print tweet object structure for debugging"""
    if level >= max_level:
        return
    
    indent = '  ' * level
    if hasattr(tweet, '__dict__'):
        attrs = vars(tweet)
        for key, value in attrs.items():
            if key.startswith('_'):
                continue
                
            print(f"{indent}{key}: ", end='')
            
            # Handle different types of values
            if isinstance(value, (str, int, float, bool)) or value is None:
                print(value)
            elif isinstance(value, (list, tuple)):
                print(f"[{len(value)} items]")
                if level < max_level - 1 and value:
                    print_tweet_structure(value[0], level + 1, max_level)
            elif isinstance(value, dict):
                print(f"{{{len(value)} items}}")
                for k, v in list(value.items())[:1]:
                    print(f"{indent}  {k}: {type(v)}")
            else:
                print(f"<{type(value).__name__}>")
                print_tweet_structure(value, level + 1, max_level)

# Make get_tweets an async function
async def get_tweets(client, tweets): 
    if tweets is None:
        #* get tweets
        print(f'{datetime.now()} - Getting tweets...')
        # Use await for async methods
        tweets = await client.search_tweet(QUERY, product='Top')
    else:
        wait_time = randint(8, 15)
        print(f'{datetime.now()} - Getting next tweets after {wait_time} seconds ...')
        await asyncio.sleep(wait_time) 
        # Use await for async methods
        tweets = await tweets.next()

    return tweets

# Define a main async function to wrap the core logic
async def main():
    #* login credentials
    config = ConfigParser()
    config.read('config.ini')
    username = config['X']['username']
    email = config['X']['email']
    password = config['X']['password']

    #* create a csv file
    with open('tweets.csv', 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Tweet_count', 'Username', 'Text', 'Created At', 'Retweets', 'Likes', 
                         'Tweet_ID', 'Profile_Pic', 'Media_Files', 'T_co_Links'])

    #* authenticate to X.com
    client = Client(language='en-US')

    # Use await for async methods
    print(f'{datetime.now()} - Logging in...')
    await client.login(auth_info_1=username, auth_info_2=email, password=password)
    print(f'{datetime.now()} - Logged in successfully')

    # Create a session for downloading images
    async with aiohttp.ClientSession() as session:
        tweet_count = 0
        tweets = None

        while tweet_count < MINIMUM_TWEETS:
            try:
                tweets = await get_tweets(client, tweets)
            except TooManyRequests as e:
                rate_limit_reset = datetime.fromtimestamp(e.rate_limit_reset)
                print(f'{datetime.now()} - Rate limit reached. Waiting until {rate_limit_reset}')
                wait_time = rate_limit_reset - datetime.now()
                await asyncio.sleep(wait_time.total_seconds())
                continue
            except Exception as e:
                print(f'{datetime.now()} - An error occurred: {e}')
                break

            if not tweets:
                print(f'{datetime.now()} - No more tweets found')
                break

            for tweet in tweets:
                tweet_count += 1
                tweet_text = tweet.text.replace('\n', ' ') if tweet.text else ''
                user_name = tweet.user.name if tweet.user else 'N/A'
                created_at = tweet.created_at if tweet.created_at else 'N/A'
                retweet_count = tweet.retweet_count if tweet.retweet_count is not None else 0
                favorite_count = tweet.favorite_count if tweet.favorite_count is not None else 0
                tweet_id = tweet.id if hasattr(tweet, 'id') else f"unknown_{tweet_count}"

                # Debug tweet structure for first tweet
                if tweet_count == 1:
                    print("\n----- Tweet Structure -----")
                    print_tweet_structure(tweet)
                    print("--------------------------\n")
                
                # Debug tweet structure
                print(f"\n{datetime.now()} - Processing tweet ID: {tweet.id}")
                
                # Extract t.co links from tweet text
                t_co_links = extract_links(tweet_text)
                t_co_links_str = '|'.join(t_co_links) if t_co_links else ''
                print(f"Found t.co links: {t_co_links_str}")

                # Download profile picture if available - FIXED: use profile_image_url instead
                profile_pic_path = ''
                if hasattr(tweet.user, 'profile_image_url') and tweet.user.profile_image_url:
                    # Get original size by removing _normal from URL
                    profile_pic_url = tweet.user.profile_image_url.replace('_normal', '')
                    print(f"Found profile image URL: {profile_pic_url}")
                    
                    # Sanitize filename by removing special characters
                    safe_username = re.sub(r'[^\w\s]', '', user_name).replace(' ', '_')
                    profile_pic_filename = f"{safe_username}_{tweet_id}.jpg"
                    profile_pic_path = os.path.join(PROFILE_PICS_DIR, profile_pic_filename)
                    
                    # Download the profile picture
                    downloaded_path = await download_image(session, profile_pic_url, profile_pic_path)
                    profile_pic_path = downloaded_path if downloaded_path else ''

                # Download media (images) if available
                media_paths = []
                
                # Handle twikit.media.* objects
                if hasattr(tweet, 'media') and tweet.media:
                    for i, media_item in enumerate(tweet.media):
                        media_type = type(media_item).__name__
                        print(f"Processing media item {i} of type: {media_type}")
                        
                        # For Photo type media
                        if media_type == 'Photo' and hasattr(media_item, 'media_url'):
                            media_url = media_item.media_url
                            print(f"Found photo media URL: {media_url}")
                            
                            # Create a filename for the media
                            media_filename = f"{tweet_id}_photo_{i}.jpg"
                            media_path = os.path.join(IMAGES_DIR, media_filename)
                            
                            # Download the image
                            downloaded_path = await download_image(session, media_url, media_path)
                            if downloaded_path:
                                media_paths.append(downloaded_path)
                        
                        # For Video type media
                        elif media_type == 'Video' and hasattr(media_item, 'video_info'):
                            # For videos, we'll grab the thumbnail
                            if hasattr(media_item, 'media_url'):
                                thumb_url = media_item.media_url
                                print(f"Found video thumbnail URL: {thumb_url}")
                                
                                # Create a filename for the video thumbnail
                                media_filename = f"{tweet_id}_video_thumb_{i}.jpg"
                                media_path = os.path.join(IMAGES_DIR, media_filename)
                                
                                # Download the thumbnail
                                downloaded_path = await download_image(session, thumb_url, media_path)
                                if downloaded_path:
                                    media_paths.append(downloaded_path)
                        
                        # For AnimatedGif type media
                        elif media_type == 'AnimatedGif' and hasattr(media_item, 'media_url'):
                            thumb_url = media_item.media_url
                            print(f"Found animated GIF thumbnail URL: {thumb_url}")
                            
                            # Create a filename for the GIF thumbnail
                            media_filename = f"{tweet_id}_gif_thumb_{i}.jpg"
                            media_path = os.path.join(IMAGES_DIR, media_filename)
                            
                            # Download the thumbnail
                            downloaded_path = await download_image(session, thumb_url, media_path)
                            if downloaded_path:
                                media_paths.append(downloaded_path)
                        
                        # For any other unknown types, try to access common properties
                        elif hasattr(media_item, 'media_url'):
                            media_url = media_item.media_url
                            print(f"Found media URL from unknown type: {media_url}")
                            
                            # Create a filename for the media
                            media_filename = f"{tweet_id}_unknown_{i}.jpg"
                            media_path = os.path.join(IMAGES_DIR, media_filename)
                            
                            # Download the image
                            downloaded_path = await download_image(session, media_url, media_path)
                            if downloaded_path:
                                media_paths.append(downloaded_path)

                # Join media paths with a separator for CSV storage
                media_paths_str = '|'.join(media_paths) if media_paths else ''

                tweet_data = [
                    tweet_count, user_name, tweet_text, created_at,
                    retweet_count, favorite_count, tweet_id,
                    profile_pic_path, media_paths_str, t_co_links_str
                ]

                with open('tweets.csv', 'a', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(tweet_data)

                if tweet_count >= MINIMUM_TWEETS:
                    break

            print(f'{datetime.now()} - Got {tweet_count} tweets')
            if tweet_count >= MINIMUM_TWEETS:
                break

        print(f'{datetime.now()} - Done! Got {tweet_count} tweets found')

# Run the main async function
if __name__ == "__main__":
    asyncio.run(main())