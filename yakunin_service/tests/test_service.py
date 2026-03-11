"""Test the service."""

import datetime
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
import requests

from yakunin.tests.conftest import ARCHIVES_DIR
from yakunin_service.utils import PORT

from .conftest import process_response, suffix


@pytest.mark.parametrize(
    "websocket_name",
    [
        # without feedback channel (situation around summer 2025)
        "",
        # with feedback channel
        "test_ws_name",
    ],
)
def test_send_pdf(
    yakunin_service: Callable,
    tmp_path: Path,
    websocket_name: str,
):
    """Send a tex and get back a PDF."""
    url = f"http://localhost:{PORT}/mkpdf/"
    in_fname = Path(ARCHIVES_DIR) / "01-test.tex"
    with in_fname.open(mode="rb") as in_fhandle:
        response = requests.post(
            url,
            files={"file": in_fhandle},
            data={"feedback_ws_url": websocket_name},
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


def test_concurrent_conversions_independent_tasklogs(
    yakunin_service: Callable,
    tmp_path: Path,
):
    """Test that the logs of the task are independent of other tasks."""
    url = f"http://localhost:{PORT}/mkpdf/"

    fname_1 = "01-test.tex"  # NB: note that the file-names are different!
    fname_2 = "10-test-tex"
    fpath_1 = Path(ARCHIVES_DIR) / fname_1
    fpath_2 = Path(ARCHIVES_DIR) / fname_2
    import concurrent.futures

    def make_request(fname) -> requests.Response:
        """Make a single request to the service."""
        with fname.open(mode="rb") as in_fhandle:
            return requests.post(
                url,
                files={"file": in_fhandle},
                timeout=11,
            )

    # Make two concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(make_request, fpath_1)
        future2 = executor.submit(make_request, fpath_2)

        response1 = future1.result()
        response2 = future2.result()

    # Maybe a bit weak as test: we expect to find references to the
    # processed file only in the task-log of the relative request.
    out_content1 = process_response(response1, tmp_path, "request1")
    out_content2 = process_response(response2, tmp_path, "request2")
    assert fname_1 in out_content1
    assert fname_1 not in out_content2
    assert fname_2 in out_content2
    assert fname_2 not in out_content1
