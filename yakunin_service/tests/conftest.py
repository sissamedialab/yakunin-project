"""Test the service."""

import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests
from filelock import FileLock

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


def process_response(response: requests.Response, tmp_path: Path, output_name: str) -> str:
    """
    Process a response from the yakunin service.

    Extract the tar.gz and find the task-log.

    Args:
        response: The HTTP response from the service
        tmp_path: Temporary directory for extraction
        output_name: Name prefix for output files

    Returns:
        The text content of the task-log

    """
    assert response.status_code == 200
    out_fname = tmp_path / f"{output_name}.tar.gz"
    out_fname.write_bytes(response.content)

    extract_dir = tmp_path / output_name
    extract_dir.mkdir(exist_ok=True)

    subprocess.run(
        args=("tar", "xf", out_fname, "-C", extract_dir),
        check=True,
    )
    return (extract_dir / "yakunin-task.log").read_text()


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
