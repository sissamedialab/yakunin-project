"""Test the transformation of a file to PDF/A-1b
I do not test the validity of the PDF/A file,
I only test the process workflow and behavior.
"""

import copy
import os

import pytest
from conftest import ARCHIVES_DIR, well_formed

from yakunin.archive import Archive
from yakunin.lib import TASK_LOG, aruspica_mime


@pytest.mark.skip("TODO")
def test_simple_pdf(setup_config):
    "Transform a simple pdf into PDF/A-1b"
    pdf_file = "14-test.pdf"
    pdf_file_path = os.path.join(ARCHIVES_DIR, pdf_file)
    archive = Archive(archive=pdf_file_path)
    archive.topdfa(**vars(setup_config))

    result = archive.submission_archive()
    with well_formed(result) as (tmp_dir, files):
        assert archive.main_pdf in files
        assert (
            aruspica_mime(os.path.join(tmp_dir, archive.main_pdf)) == "application/pdf"
        )


@pytest.mark.skip("TODO")
def test_wrong_server(setup_config):
    "Send for PDF/A-1b transformation to wrong server (server return 200)"
    pdf_file = "14-test.pdf"
    pdf_file_path = os.path.join(ARCHIVES_DIR, pdf_file)
    archive = Archive(archive=pdf_file_path)
    setup_config = copy.deepcopy(setup_config)
    setup_config.pdfa_url = "https://medialab.sissa.it/"
    archive.topdfa(**vars(setup_config))

    result = archive.submission_archive()
    with well_formed(result) as (tmp_dir, files):
        assert archive.main_pdf not in files
        with open(os.path.join(tmp_dir, TASK_LOG)) as src:
            log_lines = src.readlines()
            expected_text = "ERROR PDF/A transformation failed."
            f" Server {setup_config.pdfa_url} returned text/html file.\n"
            assert expected_text in log_lines


@pytest.mark.skip("TODO")
def test_non_200(setup_config):
    "Send for PDF/A-1b transformation to wrong page (get non-200 code)"
    # TODO: generalize with previous tests
    pdf_file = "14-test.pdf"
    pdf_file_path = os.path.join(ARCHIVES_DIR, pdf_file)
    archive = Archive(archive=pdf_file_path)
    setup_config = copy.deepcopy(setup_config)
    setup_config.pdfa_url = "https://medialab.sissa.it/non-existent"
    archive.topdfa(**vars(setup_config))

    result = archive.submission_archive()
    with well_formed(result) as (tmp_dir, files):
        assert archive.main_pdf not in files
        with open(os.path.join(tmp_dir, TASK_LOG)) as src:
            log_lines = src.readlines()
            expected_text = f"ERROR PDF/A transformation failed. Server {setup_config.pdfa_url} returned code 404.\n"
            assert expected_text in log_lines
