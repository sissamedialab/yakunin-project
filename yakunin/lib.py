"""Extract, compile & watermark WJ TeX archives."""

import bz2
import gzip
import logging
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import patoolib

from yakunin.exceptions import UnknownArchiveFormatError

YAKUNIN_LOGGER = logging.getLogger("yakunin")
TASK_LOGGER_NAME = "yakunin.task"
task_logger = logging.getLogger(TASK_LOGGER_NAME)
TASK_LOGFILE_NAME = "yakunin-task.log"
PITSTOP_NS = {"tr": "http://www.enfocus.com/PitStop/13/PitStopServerCLI_TaskReport.xsd"}


def get_task_logger(basedir: Path) -> logging.Logger:
    # This logger writes to a "yakunin-task.log" file in the temp_dir
    # all relevant steps of the required task. This task log
    # is meant to be used to communicate with the calling application.
    # Now I know where temp_dir is, so here I change the logger's
    # handler filename
    logger = logging.getLogger(TASK_LOGGER_NAME)
    handler = logging.FileHandler(basedir / TASK_LOGFILE_NAME)
    formatter = logging.Formatter("%(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger


def aruspica_mime(archive_filename: str) -> str:
    """
    Epatoscopia del file per determinarne il tipo.

    Restituisce una tupla con mime type (output di file) e formato di
    decompressione suggerito per shutil.

    Raises:
      RuntimeError: if a compressed tar archive was not a tar.

    """
    # seems easy, but libraries mimetypes,
    # magic (python-magic) and filetype only give the "outermost" type
    # i.e., tar.gz → gz
    # .docx → zip
    # or do not know tex files (text/x-tex)

    # Using "file"
    result = subprocess.run(
        args=["file", "-b", "--mime-type", archive_filename],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
    )
    mime_type = result.stdout.strip()

    task_logger.debug(
        'Mime type of "%s" appears to be "%s"',
        archive_filename,
        mime_type,
    )

    # for doubtful mime_types, do a "first" extraction
    # and check what you get

    # Please note that mime type of tar.gz is debated:
    # https://superuser.com/a/960710/203364
    pesky_ones = {
        "application/gzip": {
            "shutil_format": "gz",
            "possible_mime": "application/x-compressed-tar",
        },
        "application/x-bzip2": {
            "shutil_format": "bz",
            "possible_mime": "application/x-bzip-compressed-tar",
        },
    }
    tmpdir = tempfile.mkdtemp()
    if mime_type in pesky_ones:
        shutil.unpack_archive(
            archive_filename,
            tmpdir,
            pesky_ones[mime_type]["shutil_format"],
        )

        files = os.listdir(tmpdir)
        if len(files) != 1:
            raise RuntimeError(f"Expected one file, found {len(files)}. Please check!")

        result = subprocess.run(
            args=["file", "-b", "--mime-type", os.path.join(tmpdir, files[0])],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
        )
        internal_mime_type = result.stdout.strip()
        if internal_mime_type == "application/x-tar":
            mime_type = pesky_ones[mime_type]["possible_mime"]
            task_logger.debug(
                'Mime type of "%s" is actually "%s"',
                archive_filename,
                mime_type,
            )
    shutil.rmtree(tmpdir)

    # TODO: do the same for zip file that could be odt or docx
    return mime_type


def gunzip_something(src, work_dir):
    """Gunzip the given gzipped file."""
    src_basename = os.path.split(src)[-1]
    # remve ".gz" from filename
    src_basename = re.sub(r"(\.gz)?$", "", src_basename, flags=re.IGNORECASE)
    with (
        gzip.open(src, "rb") as f_in,
        open(
            os.path.join(work_dir, src_basename),
            "wb",
        ) as f_out,
    ):
        shutil.copyfileobj(f_in, f_out)


def bunzip2_something(src, work_dir):
    """Bunzip2 the given bzipped file."""
    src_basename = os.path.split(src)[-1]
    # remve ".bz2" from filename
    src_basename = re.sub(r"(\.bz2)?$", "", src_basename, flags=re.IGNORECASE)
    with (
        bz2.open(src, "rb") as f_in,
        open(
            os.path.join(work_dir, src_basename),
            "wb",
        ) as f_out,
    ):
        shutil.copyfileobj(f_in, f_out)


def just_copy(src, work_dir):
    """Just copy src into work_dir."""
    src_basename = os.path.split(src)[-1]
    with (
        open(src, "rb") as f_in,
        open(
            os.path.join(work_dir, src_basename),
            "wb",
        ) as f_out,
    ):
        shutil.copyfileobj(f_in, f_out)


def use_patool(src, work_dir):
    """
    Extract an archive using "patool" (which relies on external commands.

    Raises:
      UnknownArchiveFormatError: if the archive format is unknown.

    """
    try:
        # TODO: redirect patool stderr to task_logger
        patoolib.extract_archive(src, outdir=work_dir, verbosity=-1)
    except patoolib.util.PatoolError:
        task_logger.error("Cannot extract %s.", src)  # noqa: TRY400
        YAKUNIN_LOGGER.exception("patoolib error during extraction")

        # ok, non è proprio l'error corretto, ma pazienza :)
        raise UnknownArchiveFormatError from patoolib.util.PatoolError


shutil.register_unpack_format(
    "gz",
    [
        "gz",
    ],
    gunzip_something,
)

shutil.register_unpack_format(
    "bz",
    [
        "bz2",
    ],
    bunzip2_something,
)

shutil.register_unpack_format(
    "copy",
    [
        "tex",
    ],
    just_copy,
)

shutil.register_unpack_format(
    "any",
    [
        "rar",
    ],
    use_patool,
)


DOCUMENTCLASS = re.compile(r"^[^%]*\\documentclass")


def has_documentclass(filename):
    r"""
    Find if the file has a \documentclass.

    Returns True if the given file contains the string \documentclass
    (without comments before it) in its first lines.

    """
    found = False
    limit = 101
    count = 1
    with open(filename, encoding="utf-8") as src:
        for line in src:
            if count > limit:
                break
            if re.search(DOCUMENTCLASS, line):
                found = True
                break
            count += 1
    return found


def text_of_tags(query, ffile):
    """Return all texts values of the "query" tags in the given xml "ffile"."""
    root = ET.parse(ffile).getroot()
    messages = root.findall(query)
    return "\n".join([msg.text for msg in messages])


def read_pitstop_report(file_zip, task_report_fn, report_fn, task=None):
    """
    Check the pitstop report.

    Check if the given pitstop xml reports are in the zip file and log
    the (number of) fixes, errors and critical failures.

    """
    where = task_report_fn
    if task is not None:
        where = task
    has_errors = False
    response_files = file_zip.namelist()
    if task_report_fn in response_files:
        task_report = file_zip.open(task_report_fn)

        root = ET.parse(task_report).getroot()
        # TODO: review me!
        # ? # fix_fixes = root.find(
        # ? #     'tr:ProcessResults/tr:Fixes',
        # ? #     namespaces=PITSTOP_NS).text

        # TODO: should I behave differently with Errors and Critical Failures?
        errors = root.find("tr:ProcessResults/tr:Errors", namespaces=PITSTOP_NS).text
        if int(errors) > 0:
            has_errors = True
            report = file_zip.open(report_fn)
            errors = text_of_tags(
                "Report/PreflightResult/PreflightResultEntry"
                "[@type='Check'][@level='error']/PreflightResultEntryMessage/"
                "Message",
                report,
            )
            task_logger.error(
                "Errors in %s! First is:  %s",
                where,
                errors.replace(r"\n", " ⤶ "),
            )

        fails = root.find("tr:ProcessResults/tr:Failures", namespaces=PITSTOP_NS).text
        if int(fails) > 0:
            has_errors = True
            report = file_zip.open(report_fn)
            fails = text_of_tags(
                "Report/PreflightResult/PreflightResultEntry"
                "[@level='criticalfailures']/PreflightResultEntryMessage/"
                "Message",
                report,
            )
            task_logger.error(
                "Critical failures in %s! First is:  %s",
                where,
                fails.replace(r"\n", " ⤶ "),
            )
    else:
        task_logger.error("Error: expected %s is missing...", task_report_fn)

    return has_errors


def verify_environment() -> list[[str, str]]:
    """Test that we have what's needed to compile etc."""
    results = []

    intermediate = ""
    available_formats = [x[0] for x in shutil.get_archive_formats()]
    for formato in ["gztar", "zip", "bztar", "xztar"]:
        if formato in available_formats:
            intermediate += f" 🟢 {formato} ok\n"
        else:
            intermediate += f" 🔴 {formato} missing\n"
    result = ["All needed archive formats are available to shutil", intermediate]
    results.append(result)

    # https://tex.stackexchange.com/a/52994/56076
    process = subprocess.run(
        args=["kpsewhich", "-var-value=max_print_line"],
        check=True,
        stdout=subprocess.PIPE,
    )
    max_print_line = int(process.stdout.decode("utf-8").strip())
    if max_print_line > 999:
        intermediate = f" 🟢 {max_print_line} ok\n"
    else:
        intermediate = f" 🔴 {max_print_line} is too short\n"
    results.append(("TeX log lines are long enough", intermediate))

    intermediate = ""
    for program in [
        "latex",
        "pdftk",  # for watermarks
        "gs",  # for watermarks
        "libreoffice",  # for odt-to-pdf
    ]:
        if shutil.which(program) is None:
            intermediate += f" 🔴 {program} missing\n"
        else:
            intermediate += f" 🟢 {program} ok\n"
    results.append(("The required programs are installed on the system", intermediate))
    return results
