from flask import Blueprint, render_template, jsonify, request, send_from_directory
from flask_login import login_required, logout_user, current_user
from app.reddit_scraper import scrape_reddit_story
from app.text_to_speech import text_to_speech
from app.video_processing import adjust_video_for_tiktok, overlay_text_on_video, generate_subtitles
from app.story_rewriter import rework_story_with_product
import uuid
from .models import Story
import os
import moviepy.editor as mp
from . import db
from app.socketio_instance import socketio

views = Blueprint('views', __name__)


@views.route('/views', methods=['GET', 'POST'])
@login_required
def index():
    return render_template('index.html', user = current_user)

@views.route('/generated_files/<path:filename>')
def serve_generated_file(filename):
    return send_from_directory('../generated_files', filename, mimetype='video/mp4')

@views.route('/get_story', methods=['GET'])
def get_story():
    subreddit_name = request.args.get('subreddit', 'news')
    title, story_text = scrape_reddit_story(subreddit_name)
    if not title or not story_text:
        return jsonify({'error': f"No text-based stories found in /r/{subreddit_name}"}), 500
    return jsonify({'title': title, 'story_text': story_text})

@views.route('/modify_story', methods=['POST'])
def modify_story():
    data = request.get_json()
    story = data.get('story')
    product = data.get('product')

    if not story or not product:
        return jsonify({'error': 'Story and product are required'}), 400

    modified_story = rework_story_with_product(story, product)
    return jsonify({'modified_story': modified_story})

@views.route('/generate', methods=['POST'])
def generate():
    """Handles the generation of story, title, text-to-speech, video adjustment, and overlay processes."""
    gameplay = request.form['gameplay']
    voice = request.form['voice']
    title = request.form['title']
    story_text = request.form['story_text']
    product = request.form['product']  # Get the product info from the form
    username = request.form['username']  # Get the username from the form
    profile_pic = request.files['profilePicture']  # Get profile picture

    try:
        # Save profile picture to a specific path
        profile_pic_path = f"./generated_files/profile_{uuid.uuid4()}.png"
        profile_pic.save(profile_pic_path)

        # Call the OpenAI API to rework the story with the product
        reworked_story = rework_story_with_product(story_text, product)

        new_story = Story(data = story_text, title = title, gptdata = reworked_story, 
                          user_id = current_user.id)
        
        db.session.add(new_story)

        # socketio.emit('log_update', {'log': "Log: Generating text-to-speech for title..."})
        title_audio_path = text_to_speech(title, voice=voice)

        # socketio.emit('log_update', {'log': "Log: Generating text-to-speech for story..."})
        story_audio_path = text_to_speech(reworked_story, voice=voice)

        if not title_audio_path or not story_audio_path:
            raise ValueError("Error: Audio paths for title or story are None.")
        socketio.emit('log_update', {'log': f"Log: Audio paths verified. Title audio path: {title_audio_path}, Story audio path: {story_audio_path}"})

        if gameplay == 'subway-surfers':
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

        if not subtitles:
            raise ValueError("Error: subtitle creation failed.")

        socketio.emit('log_update', {'log': "Log: Starting overlay of text on video..."})
        tiktok_video = overlay_text_on_video(adjusted_video, title_audio_path, story_audio_path, title, reworked_story, subtitles, username, profile_pic_path)

        if not tiktok_video:
            raise ValueError("Error: Video overlay failed.")

        video_url = f"app/generated_files/{os.path.basename(tiktok_video)}"
        socketio.emit('video_generated', {'video_url': video_url})

        socketio.emit('process_complete', {'video_url': video_url})
        return jsonify({'full_story': reworked_story, 'title': title, 'story_audio_path': story_audio_path, 'title_audio_path': title_audio_path, 'video_url': video_url})
    except Exception as e:
        socketio.emit('log_update', {'log': f"Error during generation: {e}"})
        return jsonify({'error': str(e)}), 500


