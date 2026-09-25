"""Kinescope's management API, for the admin side of video: starting an upload,
checking how processing is going, and deleting a video nothing uses any more.

Playback authorization is the other half of Kinescope (services/video.py), and
never calls out. The API key leaves this module only as a header on our own
requests; the browser gets a one-off Tus upload link instead.

Docs: docs.kinescope.com/developer-guides/file-upload-via-api
"""

from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote

import httpx

from app.core.config import get_settings

API_URL = "https://api.kinescope.io"
UPLOADER_URL = "https://uploader.kinescope.io"

# A video's status once processing has finished. Anything else (pending,
# uploading, pre-processing, processing, error, aborted, suspended) isn't playable.
DONE = "done"


class KinescopeNotConfigured(Exception):
    """No API key or project, so any request would be refused."""


class KinescopeError(Exception):
    """Kinescope refused the request or answered with something unusable."""


@dataclass(frozen=True)
class UploadLink:
    video_id: str
    endpoint: str


@dataclass(frozen=True)
class VideoState:
    status: str
    duration: float | None  # seconds, once known


class KinescopeClient:
    def __init__(self, *, api_key: str, parent_id: str, timeout: float):
        self.api_key = api_key
        self.parent_id = parent_id  # the project or folder uploads land in
        self.configured = bool(api_key and parent_id)
        # One client, one connection pool, same as the FreedomPay client.
        self.http = httpx.Client(timeout=timeout)

    def _headers(self) -> dict[str, str]:
        if not self.configured:
            raise KinescopeNotConfigured("Kinescope API key or project is not set")
        return {"Authorization": f"Bearer {self.api_key}"}

    def create_upload(self, *, title: str, filename: str, filesize: int) -> UploadLink:
        """Reserve a video and get the Tus endpoint the browser uploads it to.

        The endpoint takes no token, which is the point: the file goes from the
        admin's browser straight to Kinescope, never through this API, and the
        key never reaches the browser.
        """
        res = self.http.post(
            f"{UPLOADER_URL}/v2/init",
            headers=self._headers(),
            json={
                "type": "video",
                "parent_id": self.parent_id,
                "title": title,
                "filename": filename,
                "filesize": filesize,  # Tus needs the length up front
            },
        )
        data = _data(res)
        if not data.get("id") or not data.get("endpoint"):
            raise KinescopeError("upload init returned no video id or endpoint")
        return UploadLink(video_id=data["id"], endpoint=data["endpoint"])

    def video_state(self, video_id: str) -> VideoState | None:
        """How processing is going, or None if Kinescope has no such video."""
        res = self.http.get(_video_url(video_id), headers=self._headers())
        if res.status_code == 404:
            return None
        data = _data(res)
        return VideoState(status=data.get("status", ""), duration=data.get("duration"))

    def delete_video(self, video_id: str) -> None:
        res = self.http.delete(_video_url(video_id), headers=self._headers())
        if res.status_code == 404:
            return  # already gone, which is what we wanted
        _data(res)


def _video_url(video_id: str) -> str:
    # Escaped whole, so an id containing "/" can't walk to another API path
    # with our key attached.
    return f"{API_URL}/v1/videos/{quote(video_id, safe='')}"


def _data(res: httpx.Response) -> dict:
    if res.is_error:
        try:
            message = res.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            message = res.text[:200]
        raise KinescopeError(f"kinescope answered {res.status_code}: {message}")
    try:
        return res.json()["data"]
    except (ValueError, KeyError, TypeError) as e:
        raise KinescopeError(f"unusable kinescope response: {e}") from e


@lru_cache
def get_kinescope() -> KinescopeClient:
    s = get_settings()
    return KinescopeClient(
        api_key=s.kinescope_api_key,
        parent_id=s.kinescope_folder_id or s.kinescope_project_id,
        timeout=s.kinescope_timeout_s,
    )
