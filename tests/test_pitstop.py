"""Test the validation of a file via Pitstop;
I only test the process workflow and behavior.
"""

import os
import copy
from yakunin.archive import Archive
from yakunin.lib import aruspica_mime, TASK_LOG
from conftest import ARCHIVES_DIR, well_formed


def test_simple_pdf(setup_config):
    "Pitstop-validate a simple pdf"
    pdf_file = "14-test.pdf"
    pdf_file_path = os.path.join(ARCHIVES_DIR, pdf_file)
    archive = Archive(archive=pdf_file_path)
    archive.pitstop_validate(**vars(setup_config))

    result = archive.submission_archive()
    with well_formed(result) as (tmp_dir, files):
        assert archive.main_pdf in files
        assert aruspica_mime(
            os.path.join(
                tmp_dir, archive.main_pdf)) == 'application/pdf'


def test_wrong_server(setup_config):
    "Send for pitstop validation to wrong server (server return 200)"
    pdf_file = "14-test.pdf"
    pdf_file_path = os.path.join(ARCHIVES_DIR, pdf_file)
    archive = Archive(archive=pdf_file_path)
    setup_config = copy.deepcopy(setup_config)
    setup_config.pitstop_url = "https://medialab.sissa.it/"
    archive.pitstop_validate(**vars(setup_config))

    result = archive.submission_archive()
    with well_formed(result) as (tmp_dir, files):
        assert archive.main_pdf not in files
        with open(os.path.join(tmp_dir, TASK_LOG), 'r') as src:
            log_lines = src.readlines()
            expected_text = f"ERROR Pitstop validation failed. Server {setup_config.pitstop_url} returned a text/html file.\n"
            assert expected_text in log_lines


def test_non_200(setup_config):
    "Send for pitstop validation to wrong page (get non-200 code)"
    # TODO: generalize with previous tests
    pdf_file = "14-test.pdf"
    pdf_file_path = os.path.join(ARCHIVES_DIR, pdf_file)
    archive = Archive(archive=pdf_file_path)
    setup_config = copy.deepcopy(setup_config)
    setup_config.pitstop_url = "https://medialab.sissa.it/non-existent"
    archive.pitstop_validate(**vars(setup_config))

    result = archive.submission_archive()
    with well_formed(result) as (tmp_dir, files):
        assert archive.main_pdf not in files
        with open(os.path.join(tmp_dir, TASK_LOG), 'r') as src:
            log_lines = src.readlines()
            expected_text = f"ERROR Pitstop validation failed. Server {setup_config.pitstop_url} returned code 404.\n"
            assert expected_text in log_lines
