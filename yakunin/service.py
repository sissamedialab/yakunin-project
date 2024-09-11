"""A web application server that exposes yakunin's functionalities as services."""

import argparse
import os
import sysconfig
import tempfile

import requests
import tornado.httpserver
import tornado.ioloop
import tornado.web

import yakunin
from yakunin.lib import YAKUNIN_LOGGER as logger  # NOQA N811

from .service_handlers import Mkpdf, TestService, Watermark

PORT = 8889


def make_app():
    return tornado.web.Application(
        [
            (r"/test.*", TestService),
            (r"/mkpdf.*", Mkpdf),
            (r"/watermark.*", Watermark),
            # other candidates:
            # - tex_compile
            # - pitstop_validate
            # - topdfa
            # - mkpdf
            # - find_master
            # - tideup_src
        ],
    )


def main() -> None:
    app = make_app()
    app.listen(PORT)
    setup_yakunin()
    logger.info("Started jcomassistant service")
    tornado.ioloop.IOLoop.current().start()


def stop() -> None:
    logger.info("Stopping jcomassistant service")
    tornado.ioloop.IOLoop.current().stop()


def send() -> None:
    """Send a file to an handler.

    Usefult as shell entry point.
    """
    parser = argparse.ArgumentParser(
        "Yakunin service", description="Interact with the service"
    )
    parser.add_argument("filename", help="File to send.")
    parser.add_argument("--ini", help="Optional ini file.")
    parser.add_argument(
        "--command",
        default="watermark",
        help="Command to apply. Defaults to %(default)s.",
    )
    args = parser.parse_args()
    files_to_post = {"file": open(args.filename, "rb")}
    if args.ini:
        files_to_post["ini"] = open(args.ini, "rb")
    response = requests.post(
        f"http://localhost:{PORT}/{args.command}",
        files=files_to_post,
    )
    _, fname = tempfile.mkstemp(prefix=f"{args.command}_", suffix=".tar.gz")
    with open(fname, "wb") as fd:
        fd.write(response.content)
    print(f"Result:\n{fname}")
    # TODO extract tar.gz and display it


def setup_yakunin():
    """Read and apply yakunin configuration."""
    # Get the installation path for data files
    data_path = sysconfig.get_path("data")

    # Construct the full path to the installed file
    # see pyproject.toml [tool.setuptools]
    config_file = os.path.join(data_path, "etc", "yakunin.json")

    args = argparse.Namespace()

    # Check if the file exists
    if os.path.exists(config_file):
        args.config_file = config_file
    elif os.path.exists("yakunin.json"):
        logger.warning(
            "Yakunin configuration from local folder (instead of from data path)."
            " Probably we have been installed in editable mode.",
        )
        args.config_file = "yakunin.json"
    else:
        logger.error("Yakunin configuration not found!")
        args.config_file = "Missing!"
    yakunin.merge_with_config_file(args)
