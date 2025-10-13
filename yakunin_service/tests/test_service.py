"""Test the service."""

import datetime
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest
import requests
from filelock import FileLock

from yakunin.tests.conftest import ARCHIVES_DIR
from yakunin_service.utils import PORT


def start_yakunin(port: int) -> subprocess.Popen:
    cwd = Path(__file__).parent.parent
    return subprocess.Popen(
        [sys.executable, "manage.py", "runserver", "--settings", "yakunin_service.settings_test", str(PORT)],
        cwd=cwd,
    )


def wait_yakunin(proc: subprocess.Popen) -> subprocess.Popen:
    """Wait for the server to come up."""
    for _ in range(30):  # max 3 seconds
        try:
            requests.get(f"http://localhost:{PORT}/test", timeout=0.1)
            break
        except requests.exceptions.RequestException:
            time.sleep(0.1)
    else:
        # Note that we get here only if not "break" statement was hit in the for-loop.
        proc.terminate()
        pytest.fail("could not start the server")
    return proc


@pytest.fixture(scope="session")
def yakunin_service(tmp_path_factory, worker_id):
    """Start an http service."""
    if worker_id == "master":
        # just proceed when run with a single pytest worker
        proc = start_yakunin(PORT)
        wait_yakunin(proc)
        yield
        proc.terminate()
        return

    # get the temp directory shared by all workers
    root_tmp_dir = tmp_path_factory.getbasetemp().parent

    ready_file = root_tmp_dir / "yakunin_service.ready"
    lock_file = ready_file.with_suffix(".lock")
    with FileLock(lock_file):
        if ready_file.is_file():
            # do nothing: someone else started the server
            pass
        else:
            proc = start_yakunin(PORT)
            wait_yakunin(proc)
            ready_file.touch()

    yield

    # No need to explicitly proc.terminate(), because proc dies when
    # parent process dies
    return


@pytest.mark.parametrize(
    "url",
    [
        # without feedback channel (situation around summer 2025)
        f"http://localhost:{PORT}/mkpdf/",
        # with feedback channel
        f"http://localhost:{PORT}/mkpdf/test_ws_name/",
    ],
)
def test_send_pdf(
    yakunin_service: Callable,
    tmp_path: Path,
    url: str,
):
    """Send a tex and get back a PDF."""
    in_fname = Path(ARCHIVES_DIR) / "01-test.tex"
    with in_fname.open(mode="rb") as in_fhandle:
        response = requests.post(
            url,
            files={"file": in_fhandle},
            timeout=11,
        )
    assert response.status_code == 200
    out_fname = tmp_path / "x.tar.gz"
    out_fname.write_bytes(response.content)
    subprocess.run(
        args=("tar", "xf", out_fname, "-C", tmp_path),
        check=True,
    )
    pdf_fname = tmp_path / "01-test.pdf"
    subprocess.run(
        args=("pdftotext", pdf_fname),
        check=True,
    )
    out_content = pdf_fname.with_suffix(".txt").read_text()
    # Warning: yakunin's docker image runs under UTC even when run in a non-UTC host
    # see also wjs/specs#1173
    now = datetime.datetime.now(tz=datetime.UTC)
    expected_date = now.strftime(f"%A {now.day}{suffix(now.day)} %B, %Y%H:%M")
    assert expected_date in out_content


def suffix(day):
    """Return the ordinal suffix for a day."""
    if 11 <= day <= 13:
        return "th"
    if day % 10 == 1:
        return "st"
    if day % 10 == 2:
        return "nd"
    if day % 10 == 3:
        return "rd"
    return "th"
