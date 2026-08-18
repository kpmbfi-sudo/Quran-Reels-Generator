#!/usr/bin/env python3
"""
YouTube Uploader Module - Handles OAuth2 authentication and video upload
to YouTube using the YouTube Data API v3.

Setup (one-time):
    1. Go to https://console.cloud.google.com
    2. Create a project → Enable YouTube Data API v3
    3. Create OAuth 2.0 credentials (Desktop App type)
    4. Download the client_secret.json file
    5. Run: python setup_youtube.py
    6. This generates a token.json for headless use
    
For GitHub Actions:
    Store these as repository secrets:
    - YOUTUBE_CLIENT_ID
    - YOUTUBE_CLIENT_SECRET  
    - YOUTUBE_REFRESH_TOKEN

IMPORTANT: Make sure your Google Cloud project is published (not in Testing mode)
otherwise the refresh token expires every 7 days!
Go to: OAuth consent screen → Publish App
"""

import os
import sys
import json
import logging
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent.resolve()
TOKEN_FILE = SCRIPT_DIR / "token.json"
CLIENT_SECRET_FILE = SCRIPT_DIR / "client_secret.json"

def _load_env():
    """Load variables from .env file if present."""
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v

_load_env()

# YouTube API scopes
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeUploader:
    """Handles YouTube video uploads with OAuth2 authentication."""

    def __init__(self):
        self.youtube = self._get_authenticated_service()

    def _get_authenticated_service(self):
        """Build and return authenticated YouTube API service."""
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = None

        # Method 1: Environment variables (from .env or GitHub Secrets)
        client_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
        client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
        refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

        if client_id and client_secret and refresh_token:
            logger.info("🔑 Using environment variables for YouTube auth")
            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES,
            )
            try:
                creds.refresh(Request())
            except Exception as e:
                error_msg = str(e).lower()
                if 'token' in error_msg and ('revoked' in error_msg or 'expired' in error_msg or 'invalid' in error_msg):
                    raise RuntimeError(
                        "❌ YouTube Refresh Token has EXPIRED or been REVOKED!\n"
                        "This usually happens when your Google Cloud app is in 'Testing' mode.\n\n"
                        "🔧 FIX: Either:\n"
                        "  1. Go to Google Cloud Console → OAuth consent screen → Publish App\n"
                        "  2. Or re-run 'python setup_youtube.py' and update the GitHub Secret\n"
                    ) from e
                raise

        # Method 2: token.json file (for local use)
        elif TOKEN_FILE.exists():
            logger.info("🔑 Using token.json for YouTube auth")
            with open(TOKEN_FILE, 'r') as f:
                token_data = json.load(f)

            creds = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=SCOPES,
            )

            if creds.expired:
                try:
                    creds.refresh(Request())
                    # Save refreshed token
                    self._save_token(creds)
                except Exception as e:
                    raise RuntimeError(
                        f"❌ Failed to refresh YouTube token: {e}\n"
                        "Try running 'python setup_youtube.py' again."
                    ) from e

        else:
            raise RuntimeError(
                "❌ No YouTube credentials found!\n"
                "Run 'python setup_youtube.py' first to set up authentication,\n"
                "or set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN environment variables."
            )

        return build("youtube", "v3", credentials=creds)

    def _save_token(self, creds):
        """Save credentials to token.json."""
        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes) if creds.scopes else SCOPES,
        }
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f, indent=2)
        logger.info("💾 Token saved to token.json")

    def upload(self, video_path, title, description, tags=None,
               category_id="22", privacy_status="public", made_for_kids=False):
        """
        Upload a video to YouTube.

        Args:
            video_path: Path to the video file
            title: Video title (max 100 chars)
            description: Video description (max 5000 chars)
            tags: List of tags
            category_id: YouTube category (22 = People & Blogs)
            privacy_status: "public", "private", or "unlisted"
            made_for_kids: Whether the video is made for kids

        Returns:
            video_id: The YouTube video ID
        """
        from googleapiclient.http import MediaFileUpload

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Truncate title if too long
        if len(title) > 100:
            title = title[:97] + "..."

        # Truncate description if too long
        if len(description) > 5000:
            description = description[:4997] + "..."

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": category_id,
                "defaultLanguage": "ar",
                "defaultAudioLanguage": "ar",
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": made_for_kids,
                "embeddable": True,
                "publicStatsViewable": True,
            }
        }

        # Create media upload object
        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 5,  # 5MB chunks
        )

        logger.info(f"📤 Uploading to YouTube: {title}")

        # Execute upload with retry on transient failures
        max_retries = 3
        for attempt in range(max_retries):
            try:
                request = self.youtube.videos().insert(
                    part=",".join(body.keys()),
                    body=body,
                    media_body=media,
                )

                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        progress = int(status.progress() * 100)
                        logger.info(f"  📤 Upload progress: {progress}%")

                video_id = response["id"]
                logger.info(f"✅ Upload complete! Video ID: {video_id}")
                logger.info(f"🔗 URL: https://youtu.be/{video_id}")
                return video_id

            except Exception as e:
                if attempt < max_retries - 1:
                    import time
                    wait = (attempt + 1) * 10
                    logger.warning(f"⚠️ Upload attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"❌ All upload attempts failed: {e}")
                    raise


if __name__ == "__main__":
    # Quick test
    print("YouTube Uploader Module")
    print("Run 'python setup_youtube.py' to set up authentication first.")
