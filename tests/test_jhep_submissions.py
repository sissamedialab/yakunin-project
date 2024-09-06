"""Mount jhep@bertier:/submission/jhep locally, then, call this test
file to collect info about a specific preprint. Collected info can be
used to add tests files and "expected_results.xml" configurations for
subsequent testing.

Please call as
pytest --prepare-preprint=JHEP_001P_0219 tests/test_jhep_submission.py

See also
 conftest.py::ARCHIVES_DESC
            ::pytest_addoption
            ::pytest_generate_tests
and pytest.ini (that disables the running of this specific test by default)

"""

import logging
import os
import re

import pytest

from yakunin.archive import Archive
from yakunin.lib import aruspica_mime

YAKUNIN_LOGGER = logging.getLogger("yakunin")

# arXiv number; something like 1705_10950v3
ARXIV_P = re.compile(r"^[0-9]{4,4}_[0-9]{4,5}(v[0-9])?$")


# @pytest.mark.parametrize('preprint', ['JHEP_001P_0119', ])
@pytest.mark.skip
def test_collect_preprint(mount_wjfs, preprint, setup_config):
    """Try to collect info about a specific preprint.
    Collected info must be added to expected_results.xml
    for subsequent testing."""
    os.chdir(os.path.join(mount_wjfs, preprint, "1", "submission"))
    filename = aruspica_submitted_archive(os.getcwd())
    result = Archive(archive=filename).tex_compile(timeout=300)
    print(result)
    assert 1 == 0


def aruspica_submitted_archive(basedir) -> str:
    """Try to find the submitted archive in the mess that is the submission dir
    It is not possible to simply get the oldest file there
    because the archive seems to be opened elsewhere and copied here"""

    files = os.listdir(basedir)
    archive = None
    if len(files) == 1:
        # easy: one file only → that's the archive
        archive = files[0]
        return archive

    # let's see if we have an arXiv
    arxivs = list(filter(lambda x: re.match(ARXIV_P, x), files))
    if len(arxivs) == 1:
        archive = arxivs[0]
        # should have mime-type tar/tar.gz
        assert aruspica_mime(archive) in [
            "application/x-compressed-tar",
            "application/x-bzip-compressed-tar",
        ]
        return archive

    if len(arxivs) > 1:
        YAKUNIN_LOGGER.debug("Troppi file che sembrano arXivs... " + str(arxivs))
        # boh... guess that there is a gz and a non gzipped one
        # keep the gzipped one
        gzipped_arxivs = list(filter(lambda x: x.endswith(".gz"), arxivs))
        if not gzipped_arxivs:
            # who cares, take the first one
            archive = arxivs[0]
            return archive

        # do not even check, take the first one
        archive = gzipped_arxivs[0]
        return archive

    # not an arXiv
    # we might have tar.gz, zip, tex.gz or tex
    # (in order of most probable to less probable)
    for extension in ["tar.gz", "zip", "tex.gz", "tex"]:
        candidates = list(filter(lambda x: x.endswith("." + extension), files))
        if len(candidates) == 1:
            archive = candidates[0]
            return archive

        if len(candidates) > 1:
            raise Exception(f"Troppi file {extension}... " + str(candidates))

    # let's try with the mime type
    # keep only files with interesting mime-type
    candidates = filter(
        lambda x: aruspica_mime(os.path.join(basedir, x))
        in [
            "application/zip",
            "application/x-compressed-tar",
            "application/gzip",
            "text/x-tex",
        ],
        files,
    )
    # then order by size and return the biggest (is this a good idea?)
    candidates = sorted(
        candidates,
        key=lambda x: os.stat(os.path.join(basedir, x)).st_size,
        reverse=True,
    )
    archive = list(candidates)[0]
    return archive

    assert archive is not None, "What am I missing? " + str(files)
    return archive
