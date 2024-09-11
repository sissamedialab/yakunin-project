"""Library of entry points."""

import configparser
import io
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from tornado.httpserver import HTTPRequest
from tornado.web import RequestHandler

import yakunin

logger = logging.getLogger(__name__)


class TestService(RequestHandler):
    """Echo."""

    def get(self):
        """Tell I'm well and who I am."""
        self.write(f"I'm up and running on {self.request.full_url()}\n")


class Mkpdf(RequestHandler):
    """Generate PDF from any given file.

    Honor wjs.ini.
    """

    def post(self):
        """Expect a mandatory `file` and an optional `ini`.

        `file` can be any file. We'll attempt to transform it into a PDF.

        `ini` when given, must be a wjs.ini file.
        """
        archive_path, temp_dir = get_main_file(self.request)
        options = ini_to_kwargs(self.request)

        archive = yakunin.Archive(archive=archive_path)
        archive.mkpdf(**options)
        output_archive_path = Path(archive.submission_archive())

        serve_archive(self, output_archive_path)

        logger.info(
            f"Sent back {output_archive_path.name} as per request. Cleaning {temp_dir} and {output_archive_path}",
        )
        shutil.rmtree(temp_dir)
        os.unlink(output_archive_path)


class Watermark(RequestHandler):
    """Generate PDF from any given file and watermark it.

    Honor wjs.ini.
    """

    def post(self):
        """Expect a mandatory `file` and an optional `ini`.

        `file` can be any file. We'll attempt to transform it into a PDF.

        `ini` when given, must be a wjs.ini file.
        """
        archive_path, temp_dir = get_main_file(self.request)
        options = ini_to_kwargs(self.request)

        archive = yakunin.Archive(archive=archive_path)
        archive.watermark(**options)
        output_archive_path = Path(archive.submission_archive())

        serve_archive(self, output_archive_path)

        logger.info(
            f"Sent back {output_archive_path.name} as per request. Cleaning {temp_dir} and {output_archive_path}",
        )
        shutil.rmtree(temp_dir)
        os.unlink(output_archive_path)


def get_main_file(request: HTTPRequest) -> [str, str]:
    """Extract the main file from the request and save it locally.

    Return the full path of the main file and the containing temporary dir.
    The caller should clean-up these files.
    """
    file_posted = request.files["file"][0]
    original_fname: str = file_posted["filename"]
    temp_dir = tempfile.mkdtemp()
    logger.info(f"Received {original_fname} as per request. Creating {temp_dir}")
    archive_path = os.path.join(temp_dir, original_fname)
    with open(archive_path, "wb") as f:
        f.write(file_posted["body"])
    return archive_path, temp_dir


def ini_to_kwargs(request: HTTPRequest) -> dict[str:Any]:
    """Read an ini file from the request.

    Return ini entries in the section [wjs] as a dictionary.
    """
    if "ini" not in request.files:
        return {}

    posted_ini_file = request.files["ini"][0]
    config = configparser.ConfigParser()
    config.read_file(io.StringIO(posted_ini_file["body"].decode("utf-8")))
    if "wjs" in config.sections():
        return config["wjs"]
    else:
        logger.warning(
            f'Received ini file {posted_ini_file["filename"]} does not have section "wjs".'
        )
        return {}


def serve_archive(response: RequestHandler, archive: Path):
    """Serve the given tar.gz archive as an attachment."""
    response.set_header("Content-Type", "application/gzip")
    response.set_header(
        "Content-Disposition", f'attachment; filename="{archive.name}"'
    )  # noqa E702
    with open(archive, "rb") as f:
        response.write(f.read())
