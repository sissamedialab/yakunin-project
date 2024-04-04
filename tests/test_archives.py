"Test that all archives in test-files get compiled"
import os
import pytest
from conftest import ARCHIVES_DESC, ARCHIVES_DIR
from yakunin.archive import Archive
from yakunin.lib import aruspica_mime


# TODO: archives with file size = 0 byte
# TODO: archives with illegal file names
# TODO: pstriks / dvi
# TODO: tex / pdftex (instead of latex / pdflatex)
# TODO: xelatex


@pytest.mark.parametrize('archive', ARCHIVES_DESC)
def test_compilation(archive_compilation_tester, archive, setup_config):
    "Test the compilation of the chosen archives."
    archive_compilation_tester(archive)


KNOWN_FORMATS = [
    ("01-test.tex", "text/x-tex"),
    ("02-test.tex.gz", "application/gzip"),  # actually wrong...
    ("03-test.zip", "application/zip"),
    ("04-test.tar.gz", "application/x-compressed-tar"),
    ("05-test.tar.bz2", "application/x-bzip-compressed-tar"),
    ("06-test.tgz", "application/x-compressed-tar"),
    ("07-test-tgz", "application/x-compressed-tar"),
    ("08-test-zip", "application/zip"),
    ("09-test-texgz", "application/gzip"),
    ("10-test-tex", "text/x-tex"),
    ("11-test.tex.bz2", "application/x-bzip2"),
    ("12-test-tex-bz2", "application/x-bzip2"),
    ("13-test-tar-bz2", "application/x-bzip-compressed-tar"),
    ("14-test.pdf", "application/pdf"),
    ("15-test.pdf.gz", "application/gzip"),
    ("16-test.pdf.bzip2", "application/x-bzip2"),
    ("17-test-pdf-gz", "application/gzip"),
    ("18-test-pdf-bzip2", "application/x-bzip2"),
    ("19-test.tar", "application/x-tar"),
    ("20-test-tar", "application/x-tar"),
    ("21-test.odt", "application/vnd.oasis.opendocument.text"),
    ("22-test.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("30456-Paper.rar", "application/x-rar"),
]
KNOWN_FORMATS = [(os.path.join(ARCHIVES_DIR, x[0]),
                  x[1]) for x in KNOWN_FORMATS]


@pytest.mark.parametrize('archive,mime', KNOWN_FORMATS)
def test_filetype_guessing(archive, mime, setup_config):
    "Verify the guessing of the mime type of certain files"
    found_mime = aruspica_mime(archive)
    assert found_mime == mime


TEX_MASTERS = [
    ("01-test.tex", "01-test.tex"),
    ("02-test.tex.gz", "02-test.tex"),
    ("03-test.zip", "test.tex"),
    ("04-test.tar.gz", "test.tex"),
    ("05-test.tar.bz2", "test.tex"),
    ("30437-Generative_adversarial_networks.zip", "main.tex")
    ]
TEX_MASTERS = [(os.path.join(ARCHIVES_DIR, x[0]),
                x[1]) for x in TEX_MASTERS]


@pytest.mark.parametrize('archive,master', TEX_MASTERS)
def test_tex_master_guessing(archive, master):
    "Verify the guessing of the tex master for certain archives"
    with Archive(archive=archive) as arc:
        arc.find_master()
        assert arc.tex_master == master
