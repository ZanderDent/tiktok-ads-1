import moviepy.editor as mp
import uuid
from pathlib import Path
import whisper
from flask_socketio import SocketIO, emit
from moviepy.editor import ImageClip, TextClip, CompositeVideoClip
from PIL import Image
from app.socketio_instance import socketio

last_subtitle_end_time = 0


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
        # socketio.emit('log_update', {'log': "Log: Loading video for adjustment..."})
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

        # socketio.emit('log_update', {'log': "Log: Video adjusted for TikTok format."})
        return video
    except Exception as e:
        # socketio.emit('log_update', {'log': f"Error adjusting video for TikTok: {e}"})
        return None
    

from moviepy.editor import ImageClip, TextClip, CompositeVideoClip
from PIL import Image

def create_social_media_overlay(text, username, profile_pic_path, width=1080, height=1920):
    """
    Creates a social media-style overlay with the given text and profile picture.
    Reuses an existing rounded rectangle image and uses the user's uploaded profile picture.
    
    Args:
        text (str): The main title text.
        username (str): The username to display.
        profile_pic_path (str): Path to the profile picture image.
        width (int): Width of the overlay.
        height (int): Height of the overlay.
    
    Returns:
        ImageClip: A CompositeVideoClip containing the overlay elements.
    """
    try:
        # Paths to the reused images (you may need to update this path)
        rounded_rectangle_path = "./app/static/rounded_rectangle.png"
        profile_pic_path = "./app/static/profpic.png"

        # Create the background box from the existing rounded rectangle image
        bg_image_clip = ImageClip(rounded_rectangle_path).set_duration(3).set_position(('center', 'center'))

        # Profile picture positioning
        profpic_height = 140
        padding = 20
        profpic = ImageClip(profile_pic_path).resize(height=profpic_height)
        profpic_x = (width - bg_image_clip.w) // 2 + padding  # Centered within the box with padding
        profpic_y = (height - bg_image_clip.h) // 2 + (bg_image_clip.h - profpic_height) // 2  # Centered vertically in the box
        profpic = profpic.set_position((profpic_x, profpic_y))

        if profpic is None:
            raise ValueError("Profpic creation failed.")
        
        # Username positioning
        username_clip = TextClip(
            f"@{username}", fontsize=24, color='black', font='Arial-Bold'
        )
        username_x = profpic_x + profpic.w + padding  # To the right of the profile picture
        username_y = profpic_y  # Slightly below the top of the box
        username_clip = username_clip.set_position((username_x, username_y)).set_duration(3)

        # Calculate available width for the title
        available_width = bg_image_clip.w - profpic.w - 3 * padding

        # Adjust the title text size to fit within the box
        max_fontsize = 28
        title_clip = TextClip(
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
        overlay = CompositeVideoClip([bg_image_clip, profpic, username_clip, title_clip], size=(width, height)).set_duration(3)
        return overlay
    except Exception as e:
        print(f"Error creating social media overlay: {e}")
        return None

def overlay_text_on_video(video, title_audio_path, story_audio_path, title, story_text, subtitles, username, profile_pic_path):
    global last_subtitle_end_time
    try:
        # socketio.emit('log_update', {'log': "Log: Overlaying text on video..."})

        if not title_audio_path or not story_audio_path:
            raise ValueError("Audio paths for title or story are None.")

        # Load audio files
        title_audio = mp.AudioFileClip(title_audio_path)
        story_audio = mp.AudioFileClip(story_audio_path)

        # Create the title overlay with the social media overlay during the title audio
        title_overlay = create_social_media_overlay(title, username, profile_pic_path)  # Add username and profile picture path here
        if title_overlay is None:
            raise ValueError("Title overlay creation failed.")

        # Create a video with the social media overlay for the duration of the title audio
        title_video = mp.CompositeVideoClip([video.set_duration(title_audio.duration), title_overlay.set_duration(title_audio.duration)])
        title_video = title_video.set_audio(title_audio)
        if title_video is None:
            raise ValueError("Title video creation failed.")

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
        print(f"Error creating social media overlay2: {e}")
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