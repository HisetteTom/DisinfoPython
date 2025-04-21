from twikit import Client, TooManyRequests
import time
from datetime import datetime
import csv
from configparser import ConfigParser
from random import randint
import asyncio # Import asyncio

MINIMUM_TWEETS = 20
QUERY = '(#Covid) lang:en until:2025-01-01 since:2024-01-01 -filter:retweets -filter:replies'


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
    with open('tweets.csv', 'w', newline='', encoding='utf-8') as file: # Added encoding
        writer = csv.writer(file)
        writer.writerow(['Tweet_count', 'Username', 'Text', 'Created At', 'Retweets', 'Likes'])

    #* authenticate to X.com
    #! 1) use the login credentials. 2) use cookies.
    client = Client(language='en-US')

    # Use await for async methods
    # Option 1: Login and save cookies
    # print(f'{datetime.now()} - Logging in...')
    # await client.login(auth_info_1=username, auth_info_2=email, password=password)
    # client.save_cookies('cookies.json') # Removed await
    # print(f'{datetime.now()} - Logged in and saved cookies.')

    # Option 2: Load cookies (Uncomment below and comment out login/save above for subsequent runs)
    print(f'{datetime.now()} - Loading cookies...')
    client.load_cookies('cookies.json')
    print(f'{datetime.now()} - Cookies loaded.')


    tweet_count = 0
    tweets = None

    while tweet_count < MINIMUM_TWEETS:

        try:
            # Use await when calling the async get_tweets
            tweets = await get_tweets(client, tweets) # Pass client
        except TooManyRequests as e:
            rate_limit_reset = datetime.fromtimestamp(e.rate_limit_reset)
            print(f'{datetime.now()} - Rate limit reached. Waiting until {rate_limit_reset}')
            wait_time = rate_limit_reset - datetime.now()
            await asyncio.sleep(wait_time.total_seconds()) # Use asyncio.sleep
            continue
        except Exception as e: # Catch other potential exceptions
             print(f'{datetime.now()} - An error occurred: {e}')
             break # Exit loop on other errors

        if not tweets:
            print(f'{datetime.now()} - No more tweets found')
            break

        for tweet in tweets:
            tweet_count += 1
            # Ensure text is properly encoded, handle potential None values
            tweet_text = tweet.text.replace('\n', ' ') if tweet.text else ''
            user_name = tweet.user.name if tweet.user else 'N/A'
            created_at = tweet.created_at if tweet.created_at else 'N/A'
            retweet_count = tweet.retweet_count if tweet.retweet_count is not None else 0
            favorite_count = tweet.favorite_count if tweet.favorite_count is not None else 0

            tweet_data = [
                tweet_count, user_name, tweet_text, created_at,
                retweet_count, favorite_count
            ]

            with open('tweets.csv', 'a', newline='', encoding='utf-8') as file: # Added encoding
                writer = csv.writer(file)
                writer.writerow(tweet_data)

            if tweet_count >= MINIMUM_TWEETS: # Check limit inside the loop
                 break

        print(f'{datetime.now()} - Got {tweet_count} tweets')
        if tweet_count >= MINIMUM_TWEETS: # Break outer loop if limit reached
            break


    print(f'{datetime.now()} - Done! Got {tweet_count} tweets found')

# Run the main async function
if __name__ == "__main__":
    asyncio.run(main())