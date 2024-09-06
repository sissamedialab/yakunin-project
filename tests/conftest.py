"""pytest configuration & general fixtures."""

import argparse
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET  # NOQA N817 camelcase
from contextlib import contextmanager

import pytest

import yakunin
from yakunin.__init__ import merge_with_config_file
from yakunin.archive import Archive
from yakunin.lib import TASK_LOG

# Build a list of files (archives) to test

# The list of files must be defined at test-collection time
# it cannot be "too" dynamic (by design of pytest). See
# https://stackoverflow.com/questions/52764279/
# https://stackoverflow.com/questions/50231627/
ARCHIVES_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "test-files",
)

ARCHIVES_ROOT = ET.parse(os.path.join(ARCHIVES_DIR, "expected_results.xml")).getroot()


ARCHIVES_DESC = ARCHIVES_ROOT.findall("archive")


@pytest.fixture
def setup_config(scope="module"):
    """Configure logging based on yakunin.json (if present)."""
    # ugly hack to find the config file
    # (because I'm confused about "pip install" vs "python setup.py develop")
    # this work with "develop"...
    config_file = "yakunin.json"
    # ...while this works with "pip install" (hopefully)
    if not os.path.exists(config_file):
        config_file = os.path.join(
            os.path.dirname(os.path.realpath(yakunin.__file__)),
            "..",
            "..",
            "..",
            "..",
            "etc",
            "yakunin.json",
        )

    args = argparse.Namespace()
    args.config_file = config_file
    merge_with_config_file(args)
    yield args


@pytest.fixture
def archive_compilation_tester(mount_wjfs):
    """Provide a compilation tester.

    Return a function that can read a description of a test and of its expected outcome.

    The "xml_desc" is an ElementTree.Element (see also
    tests/test-files/expected_results.xml) which contains the archive
    name to compile and a list of lines that must be present in the
    compilatin log.

    """

    def archive_compilation_tester(xml_desc):
        # compile and get the result
        # (the result is a tar.gz archive)
        name_tag = xml_desc.find("name")
        filename = name_tag.text

        archive_type = xml_desc.get("type")
        if archive_type is not None:
            if archive_type == "preprint":
                return None
                # preprints are sshfs-mounted
                # the fixture mount_wjfs ensures that
                # the filesystem is mounted/unmounted

                # the archive file to process is in
                # mounted_dir/PREPRINT/1/submission/HERE
                preprint = name_tag.get("preprint")
                assert (
                    preprint is not None
                ), f"Expecting a preprint number for {filename}"
                filename = os.path.join(
                    mount_wjfs, preprint, "1", "submission", filename
                )
            else:
                raise AssertionError(f"Unknown archive type {archive_type}")
        else:
            filename = os.path.join(ARCHIVES_DIR, filename)

        assert os.path.exists(filename)

        # read command to execute
        # (one of compile, watermark, pitstop, pdfa)
        command = xml_desc.find("command")
        if command is not None:
            command = command.text
        else:
            command = "tex_compile"

        # read command options
        # these are the options as received by the function,
        # not necessarily the command-line ones
        # E.g., tex_engine is given as "latex" on the command line
        # but translates to "latexmk -dvi -pdfps"
        # see __init__::tex_engine_choices

        # (no general options at the moment)
        options = xml_desc.find("options")
        if options is not None:
            tmp = {}
            for option in options.iter("option"):
                tmp[option.get("name")] = option.get("value")

                # I'm sorry... this is becoming ridiculous
                if option.get("is-float"):
                    tmp[option.get("name")] = float(option.get("value"))
            options = tmp
        else:
            options = {
                "timeout_compilation": 300,
            }

        archive_obj = Archive(archive=filename)
        func = getattr(archive_obj, command)
        result = func(**options)

        assert os.path.exists(result)

        # check that the resulting archive is well-formed
        with well_formed(result) as data:
            # dir where the targz has been extracted
            tmp_dir = data[0]
            files = data[1]

            # the task log contains at least the expected lines
            expected_lines = xml_desc.findall("expected-lines/line")

            with open(os.path.join(tmp_dir, TASK_LOG)) as src:
                log_lines = src.readlines()
                for expected_line in expected_lines:
                    expected_text = expected_line.text + "\n"
                    # the char "💩" in the expected text stands for "anything"
                    if expected_text.find("💩") > -1:
                        pattern = re.escape(expected_text)
                        pattern = pattern.replace("💩", ".+")
                        found = list(filter(lambda x: re.match(pattern, x), log_lines))
                        assert found, expected_text
                    else:
                        assert expected_text in log_lines

            # the pdf file is in the archive (only if a successful
            # compilation has been reported)
            if "INFO Successfully compiled" in log_lines:
                pdf = filter(lambda x: x.endswith(".pdf"), files)
                assert len(list(pdf)) == 1, "Expecting 1 and only one pdf file"

            # we may want to check for certain files in the work dir
            for expected_file in xml_desc.iter("file"):
                assert os.path.exists(os.path.join(tmp_dir, "work", expected_file.text))

    return archive_compilation_tester


# Note about scope
# https://docs.pytest.org/en/latest/fixture.html

# Pytest will only cache one instance of a fixture at a time. This
# means that when using a parametrized fixture, pytest may invoke a
# fixture more than once in the given scope.


# I think it is important that the test function using this fixture is
# not parametrized, otherwise the fixture will be called multiple times
@pytest.fixture(
    params=[
        ["bertieri", "jhep", None],
    ]
)
def mount_wjfs(request, scope="session"):
    """Mount files to test.

    JOURNAL@SERVER:JOURNALArchive/archive/papers/preprint
    into /tmp/JOURNAL (or dst if provided).

    List all preprints therein and find the submitted archive for
    each.  Yield a list of such archives.  Unmount at tear-down.

    """
    yield None
    return

    server = request.param[0]
    journal = request.param[1]
    dst = request.param[2]
    assert server is not None
    assert journal is not None

    if dst is None:
        dst = f"/tmp/{journal}"

    if not os.path.exists(dst):
        os.mkdir(dst)

    if not os.listdir(dst):
        # if destination dir is not empty
        # then I assume the sshfs has already been mounted
        # (and hope for the best)
        # see also the note above about fixture scope and parametrized
        # test functions
        subprocess.run(
            args=[
                "sshfs",
                "-o",
                "ro",
                f"{journal}@{server}:{journal}Archive/archive/papers/preprint",
                dst,
            ],
            check=True,
        )

    yield dst

    # unmount only if necessary
    # see note above...
    if os.listdir(dst):
        subprocess.run(args=["fusermount", "-u", dst], check=True)


@contextmanager
def well_formed(result_archive):
    """Check that the given tar.gz.

    It can be str or path and should contain dirs "submission", "work"
    and the task log. Yield a tuple containing the tempdir where the
    tar.gz has been extracted and the list of files therein.

    """
    try:
        tmp_dir = tempfile.mkdtemp()
        shutil.unpack_archive(result_archive, tmp_dir)
        files = os.listdir(tmp_dir)

        # the task log is in the archive
        assert TASK_LOG in files, "Missing log file"

        # work and submission dir are in the archive
        assert "work" in files, "Missing work dir"
        assert "submission" in files, "Missing submission dir"

        yield (tmp_dir, files)

    finally:
        # cleanup
        shutil.rmtree(tmp_dir)


def pytest_addoption(parser):
    """Add command line options to pytest.

    See https://docs.pytest.org/en/latest/parametrize.html
    """
    parser.addoption(
        "--prepare-preprint",
        action="append",
        default=[],
        help="preprint number that you want to test-compile",
    )

    # I cannot simply test-compile any given preprint (i.e. without
    # first collecting info in expected_results.xml) because there are
    # archives whose compilation SHOULD fail


def pytest_generate_tests(metafunc):
    """Use command-line option.

    Use the give option as parameter of test functions that require a
    fixture named "preprint".
    """
    if "preprint" in metafunc.fixturenames:
        metafunc.parametrize("preprint", metafunc.config.getoption("prepare_preprint"))
