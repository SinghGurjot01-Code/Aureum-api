import os
import json
import zipfile
import tempfile
import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS  # Add this for cross-origin requests
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize Spotify client
sp = Spotify(client_credentials_manager=SpotifyClientCredentials(
    client_id=os.getenv('SPOTIPY_CLIENT_ID'),
    client_secret=os.getenv('SPOTIPY_CLIENT_SECRET')
))

def extract_spotify_id(url, type):
    """Extract Spotify ID from URL"""
    if 'spotify.com' in url:
        if type == 'track':
            parts = url.split('/track/')
            if len(parts) > 1:
                return parts[1].split('?')[0]
        elif type == 'album':
            parts = url.split('/album/')
            if len(parts) > 1:
                return parts[1].split('?')[0]
        elif type == 'playlist':
            parts = url.split('/playlist/')
            if len(parts) > 1:
                return parts[1].split('?')[0]
    else:
        return url
    return None

def detect_spotify_type(url):
    """Detect if URL is track, album, or playlist"""
    if 'track' in url:
        return 'track'
    elif 'album' in url:
        return 'album'
    elif 'playlist' in url:
        return 'playlist'
    return None

def format_duration(ms):
    """Convert milliseconds to minutes:seconds"""
    seconds = int((ms / 1000) % 60)
    minutes = int((ms / (1000 * 60)) % 60)
    return f"{minutes}:{seconds:02d}"

def download_preview(url, filename):
    """Download preview MP3 file"""
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        print(f"Error downloading preview: {e}")
    return None

@app.route('/')
def index():
    return jsonify({
        'message': 'SpotiDL API is running!',
        'endpoints': {
            'POST /api/fetch': 'Fetch Spotify metadata',
            'GET /api/download/<type>/<id>': 'Download previews ZIP',
            'GET /api/download/track/<id>': 'Download single track preview'
        }
    })

@app.route('/api/fetch', methods=['POST'])
def fetch_spotify_data():
    try:
        data = request.get_json()
        url = data.get('url', '').strip()

        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        spotify_type = detect_spotify_type(url)
        if not spotify_type:
            return jsonify({'error': 'Invalid Spotify URL. Must be track, album, or playlist'}), 400

        spotify_id = extract_spotify_id(url, spotify_type)
        if not spotify_id:
            return jsonify({'error': 'Could not extract Spotify ID from URL'}), 400

        result = {'type': spotify_type}

        if spotify_type == 'track':
            track = sp.track(spotify_id)
            album = sp.album(track['album']['id'])

            result.update({
                'title': track['name'],
                'artists': [artist['name'] for artist in track['artists']],
                'album': track['album']['name'],
                'duration': format_duration(track['duration_ms']),
                'duration_ms': track['duration_ms'],
                'release_date': track['album']['release_date'],
                'cover_art': track['album']['images'][0]['url'] if track['album']['images'] else None,
                'preview_url': track['preview_url'],
                'external_url': track['external_urls']['spotify'],
                'composers': [artist['name'] for artist in track['artists']],
                'genres': album.get('genres', [])
            })

        elif spotify_type == 'album':
            album = sp.album(spotify_id)
            tracks = sp.album_tracks(spotify_id)

            album_tracks = []
            for item in tracks['items']:
                track_data = {
                    'id': item['id'],
                    'title': item['name'],
                    'artists': [artist['name'] for artist in item['artists']],
                    'duration': format_duration(item['duration_ms']),
                    'duration_ms': item['duration_ms'],
                    'track_number': item['track_number'],
                    'preview_url': item['preview_url'],
                    'external_url': item['external_urls']['spotify']
                }
                album_tracks.append(track_data)

            result.update({
                'title': album['name'],
                'artists': [artist['name'] for artist in album['artists']],
                'release_date': album['release_date'],
                'total_tracks': album['total_tracks'],
                'cover_art': album['images'][0]['url'] if album['images'] else None,
                'external_url': album['external_urls']['spotify'],
                'genres': album.get('genres', []),
                'tracks': album_tracks
            })

        elif spotify_type == 'playlist':
            playlist = sp.playlist(spotify_id)
            tracks_data = sp.playlist_tracks(spotify_id)

            playlist_tracks = []
            for item in tracks_data['items']:
                if item['track']:
                    track = item['track']
                    track_data = {
                        'id': track['id'],
                        'title': track['name'],
                        'artists': [artist['name'] for artist in track['artists']],
                        'duration': format_duration(track['duration_ms']),
                        'duration_ms': track['duration_ms'],
                        'album': track['album']['name'],
                        'preview_url': track['preview_url'],
                        'external_url': track['external_urls']['spotify']
                    }
                    playlist_tracks.append(track_data)

            result.update({
                'title': playlist['name'],
                'description': playlist.get('description', ''),
                'owner': playlist['owner']['display_name'],
                'total_tracks': playlist['tracks']['total'],
                'cover_art': playlist['images'][0]['url'] if playlist['images'] else None,
                'external_url': playlist['external_urls']['spotify'],
                'tracks': playlist_tracks
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'Failed to fetch data: {str(e)}'}), 500

@app.route('/api/download/<spotify_type>/<spotify_id>')
def download_previews(spotify_type, spotify_id):
    try:
        if spotify_type not in ['album', 'playlist']:
            return jsonify({'error': 'Invalid type for bulk download'}), 400

        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, f'spotiDL_{spotify_type}_{spotify_id}.zip')

        if spotify_type == 'album':
            tracks_data = sp.album_tracks(spotify_id)
            title = sp.album(spotify_id)['name']
        else:
            tracks_data = sp.playlist_tracks(spotify_id)
            title = sp.playlist(spotify_id)['name']

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for item in tracks_data['items']:
                track = item['track'] if spotify_type == 'playlist' else item
                if track and track.get('preview_url'):
                    audio_content = download_preview(track['preview_url'], f"{track['id']}.mp3")
                    if audio_content:
                        safe_name = f"{track['name']} - {', '.join([a['name'] for a in track['artists']])}.mp3"
                        safe_name = "".join(c for c in safe_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        zipf.writestr(safe_name, audio_content)

        return send_file(zip_path, as_attachment=True, download_name=f'spotiDL_{title}.zip')

    except Exception as e:
        return jsonify({'error': f'Failed to create download: {str(e)}'}), 500

@app.route('/api/download/track/<track_id>')
def download_track_preview(track_id):
    try:
        track = sp.track(track_id)
        if not track.get('preview_url'):
            return jsonify({'error': 'No preview available for this track'}), 404

        audio_content = download_preview(track['preview_url'], f"{track_id}.mp3")
        if audio_content:
            safe_name = f"{track['name']} - {', '.join([a['name'] for a in track['artists']])}.mp3"
            safe_name = "".join(c for c in safe_name if c.isalnum() or c in (' ', '-', '_')).rstrip()

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            temp_file.write(audio_content)
            temp_file.close()

            return send_file(temp_file.name, as_attachment=True, download_name=safe_name)
        else:
            return jsonify({'error': 'Failed to download preview'}), 500

    except Exception as e:
        return jsonify({'error': f'Failed to download track: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
