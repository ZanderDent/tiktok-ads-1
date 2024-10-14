import praw
import random
import logging
import os

reddit = praw.Reddit(
    user_agent=True,
    client_id=os.getenv('REDDIT_CLIENT_ID'),
    client_secret=os.getenv('REDDIT_CLIENT_SECRET')
)

def scrape_reddit_story(subreddit_name):
    try:
        subreddit = reddit.subreddit(subreddit_name)
        posts = list(subreddit.hot(limit=100))
        stories = [post for post in posts if post.is_self and post.selftext]

        if not stories:
            raise ValueError(f"No text-based stories found in /r/{subreddit_name}")

        selected_story = random.choice(stories)
        return selected_story.title, selected_story.selftext
    except Exception as e:
        logging.error(f"Error scraping subreddit /r/{subreddit_name}: {e}")
        return None, None
