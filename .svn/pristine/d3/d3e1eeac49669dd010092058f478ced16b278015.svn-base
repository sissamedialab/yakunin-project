"Test pdf generation"
import os
import re
from conftest import ARCHIVES_DIR, well_formed
from yakunin.archive import Archive
from yakunin.lib import TASK_LOG


def test_simple_pdf(setup_config):
    "Test what happens if mkpdf is called with a simple pdf"
    pdf_file = "14-test.pdf"
    pdf_file_path = os.path.join(ARCHIVES_DIR, pdf_file)
    archive = Archive(archive=pdf_file_path)
    archive.mkpdf()

    # the the tar.gz of the temp_dir and check it
    result = archive.submission_archive()
    with well_formed(result) as (tmp_dir, files):
        assert pdf_file in files

        log = 'yakunin-task_log'
        with open(os.path.join(tmp_dir, TASK_LOG), 'r') as src:
            log_lines = src.readlines()

            # the log reports that yakunin simply copied the given pdf file
            found = list(
                filter(lambda x: re.match(
                    "INFO Unpacked .+submission/14-test.pdf as copy", x),
                       log_lines))
            assert found

            # the log reports the pdf file name
            assert "INFO Main pdf is 14-test.pdf\n" in log_lines


def test_from_tex_archive():
    "mkpdf should compile the given tar.gz archive and generate a pdf"
    archive_file = "04-test.tar.gz"
    archive_file_path = os.path.join(ARCHIVES_DIR, archive_file)
    archive = Archive(archive=archive_file_path)
    archive.mkpdf()

    # the the tar.gz of the temp_dir and check it
    result = archive.submission_archive()
    with well_formed(result) as (tmp_dir, files):
        pdf_file = 'test.pdf'
        assert pdf_file in files

        with open(os.path.join(tmp_dir, TASK_LOG), 'r') as src:
            log_lines = src.readlines()

            # the log reports that yakunin extracted the tag.gz
            found = list(
                filter(lambda x: re.match(
                    r"INFO Unpacked .+submission/04-test\.tar\.gz as gztar",
                    x),
                       log_lines))
            assert found

            # the log reports that yakunin had to compile the given archive
            assert "INFO Successfully compiled test.tex\n" in log_lines

            # the log reports the pdf file name
            assert "INFO Main pdf is test.pdf\n" in log_lines


# DOCX
# see <archive> with ids like "doc-to-pdf*" in expected_results.xml


def test_from_odt():
    "odt-to-pdf"
    assert False
