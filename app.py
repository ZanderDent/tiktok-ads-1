import os
import uuid
import textwrap
import logging
import queue
import random
from openai import OpenAI
import requests
import praw
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from pathlib import Path
import moviepy.editor as mp
import whisper
from PIL import Image, ImageDraw
from moviepy.video.tools.drawing import color_gradient

# Load environment variables
load_dotenv()

# Initialize OpenAI API

# Initialize Flask app and SocketIO
app = Flask(__name__)
socketio = SocketIO(app)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


# Initialize Reddit API using PRAW for script-type app
reddit = praw.Reddit(
    client_id=os.getenv('REDDIT_CLIENT_ID'),
    client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
    username=os.getenv('REDDIT_USERNAME'),
    password=os.getenv('REDDIT_PASSWORD'),
    user_agent="script:Lion:v1.0 (by u/YourRedditUsername)"  # Customize this
)

# Global variable to track when the last subtitle ends
last_subtitle_end_time = 0

def scrape_reddit_story(subreddit_name):
    """
    Scrapes the given subreddit for user-generated text content and returns a random text-based story.
    
    Args:
        subreddit_name (str): Name of the subreddit to scrape.

    Returns:
        Tuple[str, str]: A tuple containing the title and the text of the story.
    """
    try:
        subreddit = reddit.subreddit(subreddit_name)
        posts = list(subreddit.hot(limit=100))  # Fetch 100 posts from the subreddit
        stories = []

        logging.info(f"Scraping subreddit: /r/{subreddit_name}")
        for post in posts:
            # Only consider posts that are self-posts with text (user-generated content)
            if post.is_self and post.selftext:
                logging.info(f"Found post with text: {post.title}")
                stories.append({'title': post.title, 'text': post.selftext})

        if not stories:
            raise ValueError(f"No text-based stories found in /r/{subreddit_name}")

        # Return a random story from the list
        selected_story = random.choice(stories)
        return selected_story['title'], selected_story['text']

    except Exception as e:
        logging.error(f"Error scraping subreddit /r/{subreddit_name}: {e}")
        return None, None

def text_to_speech(input_text, voice="alloy", format="mp3"):
    """
    Converts text to speech using OpenAI's TTS API and saves the audio.
    Handles splitting text if it exceeds the character limit.
    
    :param input_text: Text to be converted to speech
    :param voice: Voice to use for synthesis
    :param format: Output format for the audio
    :return: File path to the generated audio
    """
    try:
        socketio.emit('log_update', {'log': f"Log: Converting text to speech with OpenAI TTS, voice: {voice}"})

        max_length = 4096
        audio_chunks = []

        # Split the text into smaller chunks if it's too long
        if len(input_text) > max_length:
            text_parts = textwrap.wrap(input_text, max_length, break_long_words=False)
        else:
            text_parts = [input_text]

        for part in text_parts:
            response = requests.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "tts-1", 
                    "input": part,
                    "voice": voice,
                    "response_format": format  # Defaults to 'mp3'
                }
            )

            if response.status_code != 200:
                raise ValueError(f"Error from OpenAI API: {response.status_code}, {response.text}")

            # Store audio chunk
            audio_chunks.append(response.content)

        # Combine all audio chunks into a single audio file
        combined_audio_path = Path(f"./generated_files/speech_{uuid.uuid4()}.{format}")
        combined_audio_path.parent.mkdir(parents=True, exist_ok=True)

        with open(combined_audio_path, "wb") as combined_audio_file:
            for chunk in audio_chunks:
                combined_audio_file.write(chunk)

        socketio.emit('log_update', {'log': f"Log: Text converted to speech and stored locally at {combined_audio_path}"})
        socketio.emit('audio_generated', {'audio_url': str(combined_audio_path)})

        return str(combined_audio_path)
    except Exception as e:
        socketio.emit('log_update', {'log': f"Error converting text to speech: {e}"})
        return None

def create_rounded_rectangle_image(width, height, radius, color=(255, 255, 255, 230)):
    """
    Creates a rounded rectangle image with the specified dimensions and color.
    
    Args:
        width (int): Width of the image.
        height (int): Height of the image.
        radius (int): Radius of the rounded corners.
        color (tuple): RGBA color tuple for the rectangle.
    
    Returns:
        str: File path to the generated image.
    """
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Draw rounded rectangle
    draw.rounded_rectangle((0, 0, width, height), radius, fill=color)

    # Save image
    output_path = f"./static/rounded_rectangle_{uuid.uuid4()}.png"
    image.save(output_path)
    return output_path

def create_social_media_overlay(text, width=1080, height=1920):
    """
    Creates a social media-style overlay with the given text and profile picture.

    Args:
        text (str): Text to display on the overlay.
        width (int): Width of the overlay.
        height (int): Height of the overlay.

    Returns:
        ImageClip: An overlay image with the specified text and profile picture.
    """
    try:
        # Create the background box dimensions and position it
        box_width = 1000
        box_height = 200
        rounded_rectangle_path = create_rounded_rectangle_image(box_width, box_height, 20)
        bg_image_clip = mp.ImageClip(rounded_rectangle_path).set_duration(3).set_position(('center', 'center'))

        # Calculate positions within the box
        profpic_height = 140
        padding = 20
        box_center_x = (width - box_width) // 2  # Center X position of the box
        box_center_y = (height - box_height) // 2  # Center Y position of the box

        # Profile picture positioning
        profpic = mp.ImageClip('static/profpic.png').resize(height=profpic_height)
        profpic_x = box_center_x + padding  # Left position within the box with padding
        profpic_y = box_center_y + (box_height - profpic_height) // 2  # Centered vertically in the box
        profpic = profpic.set_position((profpic_x, profpic_y))

        # Username positioning
        username_clip = mp.TextClip(
            "@nicksstories1887", fontsize=24, color='black', font='Arial-Bold'
        )
        username_x = profpic_x + profpic.w + padding  # To the right of the profile picture
        username_y = box_center_y + padding  # Slightly below the top of the box
        username_clip = username_clip.set_position((username_x, username_y)).set_duration(3)

        # Calculate available width for the title
        available_width = box_width - profpic.w - 3 * padding

        # Adjust the title text size to fit within the box
        max_fontsize = 28
        title_clip = mp.TextClip(
            text,
            fontsize=max_fontsize,
            color='black',
            font='Arial-Bold',
            method='caption',
            size=(available_width, None)
        )

        # Position the title text under the username
        title_y = username_y + username_clip.h + padding // 2  # Slightly below the username
        title_clip = title_clip.set_position((username_x, title_y)).set_duration(3)

        # Combine profile picture, background box, username, and title into one overlay
        overlay = mp.CompositeVideoClip([bg_image_clip, profpic, username_clip, title_clip], size=(width, height)).set_duration(3)
        return overlay
    except Exception as e:
        socketio.emit('log_update', {'log': f"Error creating social media overlay: {e}"})
        return None

def overlay_text_on_video(video, title_audio_path, story_audio_path, title, story_text, subtitles):
    global last_subtitle_end_time
    try:
        socketio.emit('log_update', {'log': "Log: Overlaying text on video..."})

        if not title_audio_path or not story_audio_path:
            raise ValueError("Audio paths for title or story are None.")

        # Load audio files
        title_audio = mp.AudioFileClip(title_audio_path)
        story_audio = mp.AudioFileClip(story_audio_path)

        socketio.emit('log_update', {'log': f"Log: Audio clips loaded successfully. Title audio duration: {title_audio.duration}, Story audio duration: {story_audio.duration}"})

        # Create the title overlay with the social media overlay during the title audio
        title_overlay = create_social_media_overlay(title)
        if title_overlay is None:
            raise ValueError("Title overlay creation failed.")

        # Create a video with the social media overlay for the duration of the title audio
        title_video = mp.CompositeVideoClip([video.set_duration(title_audio.duration), title_overlay.set_duration(title_audio.duration)])
        title_video = title_video.set_audio(title_audio)

        # Immediate transition to the story video with subtitles
        subtitle_start_time = 0  # Start subtitles immediately with story audio

        # Create subtitle clips timed to the story audio
        txt_clips = []
        for start, end, words_chunk in subtitles:
            chunk_text = ' '.join(words_chunk)

            # Ensure that the new subtitle starts only after the previous one has ended
            if last_subtitle_end_time > start:
                start = last_subtitle_end_time
            end = start + (end - start)

            # Shorten the end time slightly to avoid overlap
            end -= 0.1  # Reducing the end time by 0.1 seconds

            # Update the global variable with the new end time
            last_subtitle_end_time = end

            # Create the main text clip for subtitles
            txt_clip = mp.TextClip(
                chunk_text,
                fontsize=72,  # Adjusted size for readability
                font='Arial-Bold',
                color='white',
                stroke_color='black',
                stroke_width=1,
                method='caption',
                size=(video.w - 200, None)  # Ensure subtitles fit properly
            ).set_position('center').set_start(start).set_duration(end - start)

            # Add the subtitle text clip to the list of clips
            txt_clips.append(txt_clip)

        # Combine subtitle clips with the story audio
        story_video = mp.CompositeVideoClip([video.set_duration(story_audio.duration)] + txt_clips).set_audio(story_audio)

        # Concatenate the title video and the story video
        final_video = mp.concatenate_videoclips([title_video, story_video.set_start(title_audio.duration)], method="compose")

        # Export the final video
        output_file = f"./generated_files/tiktok_video_{uuid.uuid4()}.mp4"
        final_video.write_videofile(output_file, codec='libx264', audio_codec='aac')

        socketio.emit('log_update', {'log': f"Log: Video generated successfully. Final video path: {output_file}"})
        return output_file

    except Exception as e:
        socketio.emit('log_update', {'log': f"Error overlaying text on video: {e}"})
        return None


def generate_subtitles(audio_path):
    """
    Generates subtitles for the given audio file using the Whisper model.
    
    Args:
        audio_path (str): Path to the audio file.
    
    Returns:
        List[Tuple[float, float, str]]: List of tuples containing start time, end time, and subtitle text.
    """
    try:
        socketio.emit('log_update', {'log': "Log: Transcribing audio to generate subtitles..."})

        # Load the Whisper model
        model = whisper.load_model("base")

        # Transcribe the audio
        result = model.transcribe(audio_path)

        # Extract segments to create subtitles with short word groups (up to 3 words at a time)
        subtitles = []
        for segment in result['segments']:
            words = segment['text'].split()
            for i in range(0, len(words), 3):
                start = segment['start'] + (i / len(words)) * (segment['end'] - segment['start'])
                end = segment['start'] + ((i + 3) / len(words)) * (segment['end'] - segment['start'])
                subtitles.append((start, end, words[i:i + 3]))

        socketio.emit('log_update', {'log': "Log: Subtitles generated successfully."})
        return subtitles
    except Exception as e:
        socketio.emit('log_update', {'log': f"Error generating subtitles: {e}"})
        return []

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
    "Do not change the events, emotions, or any important details. Here's the original story:\n\n"
    f"{story_text}\n\n"
    "Ensure that the product is included as a small part of the narrative, without altering the voice or distracting the reader."
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


def adjust_video_for_tiktok(video_path, duration):
    """
    Adjusts the input video to fit TikTok's format, ensuring it matches the desired duration.
    
    Args:
        video_path (str): Path to the video file.
        duration (float): Desired duration of the output video.
    
    Returns:
        VideoFileClip: Adjusted video clip.
    """
    try:
        socketio.emit('log_update', {'log': "Log: Loading video for adjustment..."})
        video = mp.VideoFileClip(video_path)

        # Determine the aspect ratio for TikTok (9:16)
        target_aspect_ratio = 9 / 16
        video_aspect_ratio = video.w / video.h

        # Crop or pad the video to fit the target aspect ratio
        if video_aspect_ratio > target_aspect_ratio:
            # Video is wider than target, crop the sides
            new_width = int(target_aspect_ratio * video.h)
            crop_x = (video.w - new_width) // 2
            video = video.crop(x1=crop_x, width=new_width)
        else:
            # Video is taller than target, crop the top and bottom
            new_height = int(video.w / target_aspect_ratio)
            crop_y = (video.h - new_height) // 2
            video = video.crop(y1=crop_y, height=new_height)

        # Resize to TikTok's preferred resolution (1080x1920 for portrait)
        video = video.resize(newsize=(1080, 1920))

        # Trim or loop the video to match the desired duration
        if video.duration > duration:
            video = video.subclip(0, duration)
        else:
            repeat_count = int(duration / video.duration) + 1
            video = mp.concatenate_videoclips([video] * repeat_count).subclip(0, duration)

        socketio.emit('log_update', {'log': "Log: Video adjusted for TikTok format."})
        return video
    except Exception as e:
        socketio.emit('log_update', {'log': f"Error adjusting video for TikTok: {e}"})
        return None

@app.route('/')
def index():
    return render_template('index.html')

# Serve files from the generated_files directory
@app.route('/generated_files/<path:filename>')
def serve_generated_file(filename):
    return send_from_directory('generated_files', filename)

@app.route('/modify_story', methods=['POST'])
def modify_story():
    """
    Endpoint to modify the original story with product placement using OpenAI API.
    """
    data = request.get_json()
    story = data.get('story')
    product = data.get('product')

    if not story or not product:
        return jsonify({'error': 'Story and product information are required.'}), 400

    # Modify the story with subtle product placement using the OpenAI API
    modified_story = rework_story_with_product(story, product)

    return jsonify({'modified_story': modified_story})


@app.route('/get_story', methods=['GET'])
def get_story():
    """Fetches a text-based story from the subreddit entered by the user."""
    try:
        subreddit_name = request.args.get('subreddit', 'news')  # Default subreddit to 'news' if not provided
        title, story_text = scrape_reddit_story(subreddit_name)
        if not title or not story_text:
            raise ValueError(f"No text-based stories found in /r/{subreddit_name}")

        return jsonify({'title': title, 'story_text': story_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate', methods=['POST'])
def generate():
    """Handles the generation of story, title, text-to-speech, video adjustment, and overlay processes."""
    gameplay = request.form['gameplay']
    voice = request.form['voice']
    title = request.form['title']
    story_text = request.form['story_text']
    product = request.form['product']  # Get the product info from the form

    try:
        # Call the OpenAI API to rework the story with the product
        reworked_story = rework_story_with_product(story_text, product)

        socketio.emit('log_update', {'log': "Log: Generating text-to-speech for title..."})
        title_audio_path = text_to_speech(title, voice=voice)

        socketio.emit('log_update', {'log': "Log: Generating text-to-speech for story..."})
        story_audio_path = text_to_speech(reworked_story, voice=voice)

        if not title_audio_path or not story_audio_path:
            raise ValueError("Error: Audio paths for title or story are None.")
        socketio.emit('log_update', {'log': f"Log: Audio paths verified. Title audio path: {title_audio_path}, Story audio path: {story_audio_path}"})

        if gameplay == 'subway surfers':
            video_file = "source_files/subway-surfers.mp4"
        elif gameplay == 'gta':
            video_file = "source_files/gta-video.mp4"
        elif gameplay == 'minecraft':  # Added Minecraft option
            video_file = "source_files/minecraft.mp4"
        else:
            raise ValueError("Invalid gameplay type selected.")

        if not video_file:
            raise ValueError("Error: Video file path is None.")
        socketio.emit('log_update', {'log': f"Log: Video file selected: {video_file}"})

        video_duration = mp.AudioFileClip(story_audio_path).duration

        socketio.emit('log_update', {'log': "Log: Adjusting video for TikTok..."})
        adjusted_video = adjust_video_for_tiktok(video_file, video_duration)

        if not adjusted_video:
            raise ValueError("Error: Video adjustment failed.")

        socketio.emit('log_update', {'log': "Log: Generating subtitles using Whisper..."})
        subtitles = generate_subtitles(story_audio_path)

        socketio.emit('log_update', {'log': "Log: Starting overlay of text on video..."})
        tiktok_video = overlay_text_on_video(adjusted_video, title_audio_path, story_audio_path, title, reworked_story, subtitles)

        if not tiktok_video:
            raise ValueError("Error: Video overlay failed.")

        video_url = f"/generated_files/{os.path.basename(tiktok_video)}"
        socketio.emit('video_generated', {'video_url': video_url})

        socketio.emit('process_complete', {'video_url': video_url})
        return jsonify({'full_story': reworked_story, 'title': title, 'story_audio_path': story_audio_path, 'title_audio_path': title_audio_path, 'video_url': video_url})
    except Exception as e:
        socketio.emit('log_update', {'log': f"Error during generation: {e}"})
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8000, debug=True)
