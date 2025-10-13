"""A web application server that exposes yakunin's functionalities as services."""

import argparse
import tempfile
from pathlib import Path

import requests

PORT = 8889


def send() -> None:
    """
    Send a file to an handler.

    Usefult as shell entry point.
    """
    parser = argparse.ArgumentParser(
        "Yakunin service",
        description="Interact with the service",
    )
    parser.add_argument("filename", help="File to send.")
    parser.add_argument("--ini", help="Optional ini file.")
    parser.add_argument(
        "--command",
        default="watermark",
        help="Command to apply. Defaults to %(default)s.",
    )
    args = parser.parse_args()
    files_to_post = {"file": open(args.filename, "rb")}  # noqa: SIM115
    if args.ini:
        files_to_post["ini"] = open(args.ini, "rb")  # noqa: SIM115
    response = requests.post(
        f"http://localhost:{PORT}/{args.command}",
        files=files_to_post,
        timeout=10,
    )
    fname = Path(tempfile.mkstemp(prefix=f"{args.command}_", suffix=".tar.gz")[1])
    fname.write_bytes(response.content)
    print(f"Result:\n{fname}")
    # TODO extract tar.gz and display it
