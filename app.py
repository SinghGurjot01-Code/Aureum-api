import os
import json
import zipfile
import tempfile
import requests
import yt_dlp
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
import threading
from collections import defaultdict
import base64

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize Spotify client
sp = Spotify(client_credentials_manager=SpotifyClientCredentials(
    client_id=os.getenv('SPOTIPY_CLIENT_ID'),
    client_secret=os.getenv('SPOTIPY_CLIENT_SECRET')
))

download_progress = defaultdict(dict)


def setup_cookies():
    """Setup YouTube cookies for yt_dlp in Render environment."""
    cookie_path_env = os.getenv('COOKIE_FILE')
    if cookie_path_env:
        # If secret file is provided as Render mount (e.g., /etc/secrets/COOKIE_FILE)
        if os.path.exists(cookie_path_env):
            print(f"✅ Using COOKIE_FILE from mounted secret: {cookie_path_env}")
            return cookie_path_env

        # If the environment variable *contains the cookie content itself*
        if "youtube.com" in cookie_path_env:
            print("✅ COOKIE_FILE appears to contain raw cookie data.")
            tmp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
            tmp_file.write(cookie_path_env)
            tmp_file.close()
            print(f"✅ Wrote cookies to temp file: {tmp_file.name}")
            return tmp_file.name

    # Try /etc/secrets/cookies.txt if mounted by Render
    etc_path = "/etc/secrets/COOKIE_FILE"
    if os.path.exists(etc_path):
        print(f"✅ Found cookies in {etc_path}")
        return etc_path

    # Try base64 encoded fallback
    cookies_base64 = os.getenv('YOUTUBE_COOKIES_BASE64')
    if cookies_base64:
        try:
            decoded = base64.b64decode(cookies_base64).decode('utf-8')
            tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
            tmp.write(decoded)
            tmp.close()
            print(f"✅ Decoded base64 cookies to: {tmp.name}")
            return tmp.name
        except Exception as e:
            print(f"❌ Failed to decode YOUTUBE_COOKIES_BASE64: {e}")

    print("⚠️ No valid cookie file found. YouTube downloads may be limited.")
    return None


COOKIE_FILE = setup_cookies()


def extract_spotify_id(url, kind):
    if 'spotify.com' not in url:
        return url
    parts = url.split(f"/{kind}/")
    if len(parts) > 1:
        return parts[1].split('?')[0]
    return None


def detect_spotify_type(url):
    for t in ('track', 'album', 'playlist'):
        if t in url:
            return t
    return None


def format_duration(ms):
    seconds = int((ms / 1000) % 60)
    minutes = int((ms / (1000 * 60)) % 60)
    return f"{minutes}:{seconds:02d}"


def search_youtube_query(track_name, artist_name):
    return f"{track_name} {artist_name} official audio"


def progress_hook(d, download_id):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0').strip().replace('%', '')
        try:
            download_progress[download_id]['progress'] = float(percent)
            download_progress[download_id]['status'] = 'downloading'
        except:
            pass
    elif d['status'] == 'finished':
        download_progress[download_id]['filename'] = d['filename']
        download_progress[download_id]['status'] = 'processing'


def download_full_song(track_info, download_id):
    try:
        query = search_youtube_query(track_info['name'], track_info['artists'][0]['name'])
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(tempfile.gettempdir(), f'{download_id}_%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'progress_hooks': [lambda d: progress_hook(d, download_id)],
        }

        if COOKIE_FILE and os.path.exists(COOKIE_FILE):
            print(f"🍪 Using cookies from: {COOKIE_FILE}")
            ydl_opts['cookiefile'] = COOKIE_FILE
        else:
            print("⚠️ No cookie file found, using fallback options.")
            ydl_opts.update({
                'extract_flat': False,
                'ignoreerrors': True,
                'no_check_certificate': True,
                'prefer_ffmpeg': True,
                'geo_bypass': True,
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"🔍 Searching YouTube for: {query}")
            ydl.download([f"ytsearch:{query}"])
            download_progress[download_id]['status'] = 'completed'
            download_progress[download_id]['progress'] = 100
            print(f"✅ Download completed: {track_info['name']}")

    except Exception as e:
        print(f"❌ Download error: {e}")
        download_progress[download_id]['status'] = 'error'
        download_progress[download_id]['error'] = str(e)


@app.route('/')
def index():
    return jsonify({
        'message': 'SpotiDL API is live.',
        'cookies': 'Available' if COOKIE_FILE and os.path.exists(COOKIE_FILE) else 'Missing',
        'cookie_path': COOKIE_FILE or 'None'
    })


@app.route('/api/fetch', methods=['POST'])
def fetch_spotify_data():
    try:
        url = request.get_json().get('url', '').strip()
        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        kind = detect_spotify_type(url)
        if not kind:
            return jsonify({'error': 'Invalid Spotify URL'}), 400

        spotify_id = extract_spotify_id(url, kind)
        if not spotify_id:
            return jsonify({'error': 'Failed to extract ID'}), 400

        result = {'type': kind}

        if kind == 'track':
            track = sp.track(spotify_id)
            album = sp.album(track['album']['id'])
            result.update({
                'title': track['name'],
                'artists': [a['name'] for a in track['artists']],
                'album': track['album']['name'],
                'duration': format_duration(track['duration_ms']),
                'cover_art': track['album']['images'][0]['url'] if track['album']['images'] else None,
                'preview_url': track['preview_url'],
                'spotify_id': track['id'],
                'genres': album.get('genres', [])
            })
        elif kind == 'album':
            album = sp.album(spotify_id)
            tracks = sp.album_tracks(spotify_id)
            result.update({
                'title': album['name'],
                'artists': [a['name'] for a in album['artists']],
                'tracks': [{
                    'title': t['name'],
                    'artists': [a['name'] for a in t['artists']],
                    'duration': format_duration(t['duration_ms']),
                    'spotify_id': t['id']
                } for t in tracks['items']]
            })
        elif kind == 'playlist':
            playlist = sp.playlist(spotify_id)
            result.update({
                'title': playlist['name'],
                'owner': playlist['owner']['display_name'],
                'tracks': [{
                    'title': t['track']['name'],
                    'artists': [a['name'] for a in t['track']['artists']],
                    'duration': format_duration(t['track']['duration_ms']),
                    'spotify_id': t['track']['id']
                } for t in playlist['tracks']['items'] if t['track']]
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/full/track', methods=['POST'])
def download_full_track():
    try:
        spotify_id = request.get_json().get('spotify_id')
        if not spotify_id:
            return jsonify({'error': 'No track ID provided'}), 400

        track = sp.track(spotify_id)
        download_id = f"dl_{spotify_id}_{threading.get_ident()}"

        thread = threading.Thread(target=download_full_song, args=(track, download_id))
        thread.daemon = True
        thread.start()

        return jsonify({
            'download_id': download_id,
            'track': track['name'],
            'artist': [a['name'] for a in track['artists']],
            'cookies_available': bool(COOKIE_FILE and os.path.exists(COOKIE_FILE))
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/progress/<download_id>')
def get_download_progress(download_id):
    return jsonify(download_progress.get(download_id, {}))


@app.route('/api/download/file/<download_id>')
def download_file(download_id):
    data = download_progress.get(download_id, {})
    if data.get('status') != 'completed':
        return jsonify({'error': 'Download not completed yet'}), 400

    file_path = data.get('filename')
    if not file_path or not os.path.exists(file_path):
        return jsonify({'error': 'File missing'}), 404

    safe_name = os.path.basename(file_path).replace('.webm', '.mp3').replace('.m4a', '.mp3')
    return send_file(file_path, as_attachment=True, download_name=safe_name)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
