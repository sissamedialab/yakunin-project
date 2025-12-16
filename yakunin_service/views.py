import configparser
import dataclasses
import json
import logging
import shutil
import ssl
import tempfile
from base64 import b64encode
from pathlib import Path
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from websockets.sync.client import ClientConnection, connect

import yakunin

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class WSLogger:
    """Utility class used to send messages to websocket feedback channel."""

    feedback_ws_url: str
    """The channel (websocket group) where to log a message."""
    feedback_ws: ClientConnection = dataclasses.field(default=None, init=False)

    def __post_init__(self):
        if self.feedback_ws_url:
            try:
                if self.feedback_ws_url.startswith("wss://") and settings.DEBUG:
                    # Allow for self-signed certificates during development:
                    ssl_context = ssl.SSLContext()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    self.feedback_ws = connect(self.feedback_ws_url, ssl=ssl_context)
                else:
                    self.feedback_ws = connect(self.feedback_ws_url)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    f"Could not connect to websocket {self.feedback_ws_url}: {e}",
                )

    def _send(self, status: str, msg: str, data: str | None = None):
        """Send a message to the feedback websocket."""
        if not self.feedback_ws_url or not self.feedback_ws:
            return
        message_type = "completed.data" if data else "feedback.message"

        self.feedback_ws.send(
            json.dumps(
                {
                    "type": message_type,
                    "message": {
                        "status": status,
                        "text": msg,
                        "data": data,
                    },
                },
            ),
        )

    def completed(self, msg: str, content: bytes | None = None):
        """
        Log message to the websocket as completed state.

        Content of the yakunin payload can be passed to log result of the conversion.
        """
        self._send("completed", msg, b64encode(content).decode() if content else "")

    def running(self, msg: str):
        """Log message to the websocket as running state."""
        self._send("running", msg)

    def started(self, msg: str):
        """Log message to the websocket as started state."""
        self._send("started", msg)

    def debug(self, msg: str):
        """Log message to the websocket as debug state."""
        self._send("debug", msg)

    def error(self, msg: str):
        """Log message to the websocket as error state."""
        self._send("error", msg)

    def close(self):
        """Close the websocket."""
        if self.feedback_ws:
            self.feedback_ws.close()

    def __enter__(self):
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager and close the websocket."""
        self.close()
        return False


@require_http_methods(["GET"])
def test_service(request: HttpRequest) -> HttpResponse:
    """Echo."""
    return HttpResponse(f"I'm up and running on {request.build_absolute_uri()}\n")


@csrf_exempt
@require_http_methods(["POST"])
def mkpdf(request: HttpRequest) -> HttpResponse:
    """
    Generate PDF from any given file.

    Honor wjs.ini.
    Send feedback throught the given ws name.
    """
    feedback_ws_url = request.POST.get("feedback_ws_url", None)
    with WSLogger(feedback_ws_url=feedback_ws_url) as ws_logger:
        if settings.DEBUG:
            ws_logger.started("🎌 PDF generation started...")
        else:
            ws_logger.started("PDF generation started...")
        try:
            archive_path, temp_dir = get_main_file(request)
            ws_logger.running(f"Working on {archive_path}")
            options = ini_to_kwargs(request)
            ws_logger.debug(f"Options: {options}")
            archive = yakunin.Archive(archive=archive_path)
            archive.mkpdf(**options)
            output_archive_path = Path(archive.submission_archive())
            ws_logger.running("mkpdf completed")

            with output_archive_path.open(mode="rb") as f:
                file_data = f.read()

            response = HttpResponse(file_data, content_type="application/gzip")
            response["Content-Disposition"] = f'attachment; filename="{output_archive_path.name}"'

            logger.info(
                f"Sending back {output_archive_path.name} as per request. "
                f"Cleaning {temp_dir} and {output_archive_path}",
            )
            shutil.rmtree(temp_dir)
            Path(output_archive_path).unlink()
            ws_logger.completed("Sending back response.", file_data)
        except Exception as e:
            ws_logger.error(str(e))  # noqa: TRY400
            logger.exception(
                "Raised exception during conversion",
            )
            response = HttpResponse(str(e), status=500)

    return response


@csrf_exempt
@require_http_methods(["POST"])
def watermark(request: HttpRequest) -> HttpResponse:
    """
    Generate PDF from any given file and watermark it.

    Honor wjs.ini.
    """
    feedback_ws_url = request.POST.get("feedback_ws_url", None)
    with WSLogger(feedback_ws_url=feedback_ws_url) as ws_logger:
        if settings.DEBUG:
            ws_logger.started("🎌 PDF generation started...")
        else:
            ws_logger.started("PDF generation started...")
        try:
            archive_path, temp_dir = get_main_file(request)
            ws_logger.running(f"Working on {archive_path}")
            options = ini_to_kwargs(request)
            ws_logger.debug(f"Options: {options}")

            archive = yakunin.Archive(archive=archive_path)
            archive.watermark(**options)
            output_archive_path = Path(archive.submission_archive())
            ws_logger.running("watermark applied")

            with output_archive_path.open(mode="rb") as f:
                file_data = f.read()

            response = HttpResponse(file_data, content_type="application/gzip")
            response["Content-Disposition"] = f'attachment; filename="{output_archive_path.name}"'

            logger.info(
                f"Sending back {output_archive_path.name} as per request. "
                f"Cleaning {temp_dir} and {output_archive_path}",
            )
            shutil.rmtree(temp_dir)
            Path(output_archive_path).unlink()
            ws_logger.completed("Sending back response.", file_data)
        except Exception as e:
            ws_logger.error(str(e))  # noqa: TRY400
            logger.exception(
                "Raised exception during conversion",
            )
            response = HttpResponse(str(e), status=500)

    return response


def get_main_file(request: HttpRequest) -> tuple[Path, Path]:
    """
    Extract the main file from the request and save it locally.

    Return the full path of the main file and the containing temporary dir.
    The caller should clean-up these files.
    """
    file_posted = request.FILES["file"]
    original_fname: str = file_posted.name
    temp_dir = Path(tempfile.mkdtemp())
    logger.info(f"Received {original_fname} as per request. Creating {temp_dir}")
    archive_path = temp_dir / original_fname
    with open(archive_path, "wb") as f:
        f.writelines(file_posted.chunks())
    return archive_path, temp_dir


def ini_to_kwargs(request: HttpRequest) -> dict[str, Any]:
    """
    Read an ini file from the request.

    Return ini entries in the section [wjs] as a dictionary.
    """
    if "ini" not in request.FILES:
        return {}

    posted_ini_file = request.FILES["ini"]
    config = configparser.ConfigParser()
    config.read_string(posted_ini_file.read().decode("utf-8"))
    if "wjs" in config.sections():
        return dict(config["wjs"])
    logger.warning(
        f'Received ini file {posted_ini_file.name} does not have section "wjs".',
    )
    return {}
