import configparser
import dataclasses
import json
import shutil
import ssl
import tempfile
from pathlib import Path
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from websockets.sync.client import ClientConnection, connect

from yakunin.archive import Archive
from yakunin.utils import app_logger as logger


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
                    ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    self.feedback_ws = connect(self.feedback_ws_url, ssl=ssl_context)
                else:
                    self.feedback_ws = connect(self.feedback_ws_url)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    f"Could not connect to websocket {self.feedback_ws_url}: {e}",
                )

    def _send(self, result: str, msg: str, data: str | None = None):
        """Send a message to the feedback websocket."""
        if not self.feedback_ws_url or not self.feedback_ws:
            return

        try:
            self.feedback_ws.send(
                json.dumps(
                    {
                        "type": "feedback.message",
                        "message": {
                            "result": result,
                            "text": msg,
                            "data": data,
                        },
                    },
                ),
            )
        except TypeError:
            logger.warning(f"Could not send feedback {result=}; {msg=}; {data=}.")

    def started(self, msg: str):
        """Log message to the websocket as started state."""
        self._send("started", msg)

    def debug(self, msg: str):
        """Log message to the websocket as debug state."""
        self._send("debug", msg)

    def info(self, msg: str):
        """Log message to the websocket as debug state."""
        self._send("info", msg)

    def error(self, msg: str):
        """Log message to the websocket as error state."""
        self._send("error", msg)

    def warning(self, msg: str):
        """Log message to the websocket as warning state."""
        self._send("warning", msg)

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

        archive_path, temp_dir = get_main_file(request)
        ws_logger.info(f"Working on {archive_path}")

        options = ini_to_kwargs(request)
        ws_logger.debug(f"Options: {options}")

        try:
            archive = Archive(archive=archive_path, extra_logger=ws_logger)
            archive.mkpdf(**options)
            output_archive_path = Path(archive.submission_archive())

        except Exception as e:  # noqa: BLE001
            ws_logger.error("Raised exception during conversion")  # noqa: TRY400
            logger.exception(str(e))
        else:
            ws_logger.info("PDF generation completed")

        file_data = output_archive_path.read_bytes()
        response = HttpResponse(file_data, content_type="application/gzip")
        response["Content-Disposition"] = f'attachment; filename="{output_archive_path.name}"'

        logger.info(
            f"Sending back {output_archive_path.name} as per request. Cleaning {temp_dir} and {output_archive_path}",
        )

        ws_logger.info(msg="Response sent back.")

        shutil.rmtree(temp_dir)
        output_archive_path.unlink()

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

        archive_path, temp_dir = get_main_file(request)
        ws_logger.info(f"Working on {archive_path}")

        options = ini_to_kwargs(request)
        ws_logger.debug(f"Options: {options}")

        try:
            archive = Archive(archive=archive_path, extra_logger=ws_logger)
            archive.watermark(**options)
            output_archive_path = Path(archive.submission_archive())

        except Exception as e:  # noqa: BLE001
            ws_logger.error("Raised exception during conversion")  # noqa: TRY400
            logger.exception(str(e))
        else:
            ws_logger.info("Watermarking process completed")

        file_data = output_archive_path.read_bytes()
        response = HttpResponse(file_data, content_type="application/gzip")
        response["Content-Disposition"] = f'attachment; filename="{output_archive_path.name}"'

        logger.info(
            f"Sending back {output_archive_path.name} as per request. Cleaning {temp_dir} and {output_archive_path}",
        )

        ws_logger.info(msg="Response sent back.")

        shutil.rmtree(temp_dir)
        output_archive_path.unlink()

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
    if "wjs" not in config.sections():
        logger.warning(
            f'Received ini file {posted_ini_file.name} does not have section "wjs".',
        )
        return {}

    # If given, the following keys should have an int value:
    known_int_keys = {
        "timeout_compilation",
        "timeout_pitstop",
        "timeout_pdfa",
        "timeout_mkpdf",
    }
    kwargs = {}
    for key, value in dict(config["wjs"]).items():
        kwargs[key] = int(value) if key in known_int_keys else value
    return kwargs
