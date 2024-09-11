"""Test the service."""


import datetime
import subprocess
import threading
from pathlib import Path

import pytest
import requests
from conftest import ARCHIVES_DIR

import yakunin
from yakunin.service import PORT


@pytest.fixture(scope="session")
def yakunin_service():
    """Start an http service."""
    thread = threading.Thread(target=yakunin.service.main)
    thread.daemon = True  # This thread dies when the main thread dies
    thread.start()
    yield
    yakunin.service.stop()


def test_send_pdf(yakunin_service, tmp_path):
    """Send a tex and get back a PDF."""
    in_fname = Path(ARCHIVES_DIR) / "01-test.tex"
    files_to_post = {"file": open(in_fname, "rb")}
    response = requests.post(
        f"http://localhost:{PORT}/mkpdf",
        files=files_to_post,
    )
    assert response.status_code == 200
    out_fname = "x.tar.gz"
    out_fname = tmp_path / out_fname
    with open(out_fname, "wb") as fd:
        fd.write(response.content)
    subprocess.run(
        args=("tar", "xf", out_fname, "-C", tmp_path),
        check=True,
    )
    pdf_fname = tmp_path / "01-test.pdf"
    subprocess.run(
        args=("pdftotext", pdf_fname),
        check=True,
    )
    with open(pdf_fname.with_suffix(".txt")) as out_txt:
        out_content = out_txt.read()
    now = datetime.datetime.now()
    expected_date = now.strftime(f"%A {now.day}{suffix(now.day)} %B, %Y%H:%M")
    assert expected_date in out_content


def suffix(day):
    """Return the ordinal suffix for a day."""
    if 11 <= day <= 13:
        return "th"
    elif day % 10 == 1:
        return "st"
    elif day % 10 == 2:
        return "nd"
    elif day % 10 == 3:
        return "rd"
    else:
        return "th"
