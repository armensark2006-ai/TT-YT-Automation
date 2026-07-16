import os
import yt_dlp
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Configuration
TIKTOK_USERNAME = ""  # Replace with the target username (without the @)
TRACKER_FILE = "uploaded_videos.txt"

def get_already_uploaded():
    """Reads our text file database to see what we've already processed."""
    if not os.path.exists(TRACKER_FILE):
        return set()
    with open(TRACKER_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def mark_as_uploaded(video_id):
    """Saves a successfully uploaded video ID to our text file database."""
    with open(TRACKER_FILE, "a") as f:
        f.write(f"{video_id}\n")

def get_all_tiktok_video_urls(username):
    """Scans a user's entire profile and gathers all video links."""
    print(f"🕵️‍♂️ Scanning @{username}'s profile for videos...")
    profile_url = f"https://www.tiktok.com/@{username}"
    
    ydl_opts = {
        'extract_flat': True,  # Fast scan: gathers URLs without downloading the video files yet
        'skip_download': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }
    
    video_urls = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(profile_url, download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    if entry and entry.get('url'):
                        video_urls.append((entry['id'], entry['url']))
        except Exception as e:
            print(f"⚠️ Could not pull profile entries (TikTok may be throttling): {e}")
            
    print(f"📊 Found {len(video_urls)} total videos on profile.")
    return video_urls

def download_single_tiktok(tiktok_url):
    ydl_opts = {
        'outtmpl': 'temp_download.mp4',
        'format': 'best',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(tiktok_url, download=True)
        description = info.get('description') or info.get('title') or 'Uploaded via Automation'
        title = info.get('title') or 'TikTok Video'
    return 'temp_download.mp4', title, description

def get_youtube_service():
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    # For automation, this will seamlessly reuse an existing login session (token) if it exists
    flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", scopes)
    credentials = flow.run_local_server(port=0)
    return build("youtube", "v3", credentials=credentials)

def upload_to_youtube(youtube, video_path, title, description):
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public"  # Keeps it private for safety review
        }
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    print(f"🎉 YouTube Upload Complete! ID: {response['id']}")

if __name__ == "__main__":
    uploaded_history = get_already_uploaded()
    all_videos = get_all_tiktok_video_urls(TIKTOK_USERNAME)
    
    # Filter out anything we have already processed in a previous run
    new_videos = [(vid_id, url) for vid_id, url in all_videos if vid_id not in uploaded_history]
    
    if not new_videos:
        print("😴 Everything is up to date. No new videos found.")
    else:
        print(f"🔥 Found {len(new_videos)} new video(s) to process!")
        
        # Authenticate once before entering the loop
        youtube_service = get_youtube_service()
        
        for vid_id, url in new_videos:
            print(f"\n🎬 Processing video ID: {vid_id}")
            try:
                video_file, title, description = download_single_tiktok(url)
                upload_to_youtube(youtube_service, video_file, title, description)
                
                # Cleanup and track success
                if os.path.exists(video_file):
                    os.remove(video_file)
                mark_as_uploaded(vid_id)
                print(f"✅ Successfully completed and logged video {vid_id}")
                
            except Exception as e:
                print(f"❌ Failed processing video {vid_id}: {e}")
                if os.path.exists('temp_download.mp4'):
                    os.remove('temp_download.mp4')