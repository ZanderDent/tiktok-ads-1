import os
from openai import OpenAI
import logging

client = OpenAI(api_key=os.getenv('OpenAI_API_KEY'))

def rework_story_with_product(story_text, product):
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    """
    Sends the story and product info to the OpenAI API to rewrite the story, 
    subtly including the product in a natural way using the chat API.
    
    Args:
        story_text (str): Original Reddit story text.
        product (str): The product to integrate into the story.
    
    Returns:
        str: The story reworked with subtle product placement.
    """
    prompt = (
    f"Rewrite the following story to subtly incorporate the product '{product}' in a way that preserves the original voice, tone, and style of the storyteller. "
    "The product should be naturally woven into the narrative without sounding promotional or forced. The storytelling style and personal tone must be kept intact. "
    "Do not change the events, emotions, or any important details. Ensure that the product is included as a small part of the narrative, without altering the voice or distracting the reader."
    "Ideally someone in the story should be using the product, but only if it fits into the narrative."
    "Here's the original story:\n\n"
    f"{story_text}\n\n"
    )


    try:
        response = client.chat.completions.create(model="gpt-4",  # Using the chat model
        messages=[
            {"role": "system", "content": "You are a creative writing assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1000)

        # Extract the reworked story from the chat response
        reworked_story = response.choices[0].message.content
        return reworked_story

    except Exception as e:
        logging.error(f"Error with OpenAI API request: {e}")
        return story_text  # Return original story in case of API failure
