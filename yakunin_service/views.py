import configparser
import dataclasses
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

import yakunin

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class WSLogger:
    """Utility class used to send messages to websocket feedback channel."""

    feedback_wsname: str
    """The channel (websocket group) where to log a message."""
    # TODO: the actual type is django.settings.config[CHANNELS][BACKEND]
    channel_layer: str = dataclasses.field(default=None, init=False)

    def __post_init__(self):
        if self.feedback_wsname:
            self.channel_layer = get_channel_layer()

    def info(self, msg: str):
        """Log a message to the channel layer."""
        if not self.feedback_wsname:
            return

        async_to_sync(self.channel_layer.group_send)(
            f"feedback_{self.feedback_wsname}",
            {
                "type": "feedback.message",
                "message": f"[{self.feedback_wsname}] {msg}",
            },
        )


@require_http_methods(["GET"])
def test_service(request: HttpRequest) -> HttpResponse:
    """Echo."""
    return HttpResponse(f"I'm up and running on {request.build_absolute_uri()}\n")


@csrf_exempt
@require_http_methods(["POST"])
def mkpdf(request: HttpRequest, feedback_wsname: str | None = None) -> HttpResponse:
    """
    Generate PDF from any given file.

    Honor wjs.ini.
    Send feedback throught the given ws name.
    """
    ws_logger = WSLogger(feedback_wsname=feedback_wsname)
    ws_logger.info("🎌 PDF generation started...")

    archive_path, temp_dir = get_main_file(request)
    ws_logger.info(f"working on {archive_path}")
    options = ini_to_kwargs(request)
    ws_logger.info(f"options: {options}")

    archive = yakunin.Archive(archive=archive_path)
    archive.mkpdf(**options)
    output_archive_path = Path(archive.submission_archive())
    ws_logger.info("mkpdf completed")

    with output_archive_path.open(mode="rb") as f:
        file_data = f.read()

    response = HttpResponse(file_data, content_type="application/gzip")
    response["Content-Disposition"] = f'attachment; filename="{output_archive_path.name}"'

    logger.info(
        f"Sending back {output_archive_path.name} as per request. Cleaning {temp_dir} and {output_archive_path}",
    )
    shutil.rmtree(temp_dir)
    Path(output_archive_path).unlink()

    ws_logger.info("🏁 PDF generation complete.")
    ws_logger.info("Sending back response.")
    return response


@csrf_exempt
@require_http_methods(["POST"])
def watermark(request: HttpRequest, feedback_wsname: str | None = None) -> HttpResponse:
    """
    Generate PDF from any given file and watermark it.

    Honor wjs.ini.
    """
    ws_logger = WSLogger(feedback_wsname=feedback_wsname)
    ws_logger.info("🎌 Watermark application started...")

    archive_path, temp_dir = get_main_file(request)
    ws_logger.info(f"working on {archive_path}")
    options = ini_to_kwargs(request)
    ws_logger.info(f"options: {options}")

    archive = yakunin.Archive(archive=archive_path)
    archive.watermark(**options)
    output_archive_path = Path(archive.submission_archive())
    ws_logger.info("watermark applied")

    with output_archive_path.open(mode="rb") as f:
        file_data = f.read()

    response = HttpResponse(file_data, content_type="application/gzip")
    response["Content-Disposition"] = f'attachment; filename="{output_archive_path.name}"'

    logger.info(
        f"Sent back {output_archive_path.name} as per request. Cleaning {temp_dir} and {output_archive_path}",
    )
    shutil.rmtree(temp_dir)
    Path(output_archive_path).unlink()

    ws_logger.info("🏁 Watermark application complete.")
    ws_logger.info("Sending back response.")
    return response


def get_main_file(request: HttpRequest) -> tuple[str, str]:
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
