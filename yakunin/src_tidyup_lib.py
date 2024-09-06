"""These functions try to correct known problems in the tex sources.

Each function deals with only one type of problem.

Each function is passed the tex source which it can modify.
Therefore these functions MUST be called sequentially
and the order of call DOES MATTER.
Functions are ordered by name

Each function in this module will be "called" by
yakunin.Archive::read_log durin log analysis.
"""

import logging
import os
import re
import shutil
import subprocess

TASK_LOGGER = logging.getLogger("yakunin.task")


def n000_fix_encoding(filename):
    r"""Re-code (if necessary) the given file.

    The default encoding of tex sources changed in 2018 from raw to
    utf-8 (see
    https://www.latex-project.org/news/latex2e-news/ltnews28.pdf). This
    means that tex sources which encoding is not ascii or utf-8 and
    which do NOT explicitly declare their encoding with
    \usepackage[xxx]{inputenc} will fail during compilation with
    "Package inputenc Error: Invalid UTF-8 byte".

    If the encoding the encoding of the given file is not ascii or
    utf-8 AND the file does not contain an uncommented
    \usepackage[xxx]{inputenc}, then I will try to re-encode the file
    into utf-8.

    This function should be called before any compilation attempt.
    """
    charset = None
    result = subprocess.run(
        args=["file", "-b", "--mime-encoding", filename],
        stdout=subprocess.PIPE,
        check=True,
        encoding="utf-8",
    )

    charset = result.stdout.strip()
    if charset not in ["us-ascii", "utf-8"]:
        if charset == "unknown-8bit":
            # assunzione...
            TASK_LOGGER.debug("%s charset is %s; assuming win-1252", filename, charset)
            charset = "cp1252"
            # per emacs è win-1252
            # per latex sarebbe \usepackage[ansinew]{inputenc}

        TASK_LOGGER.debug("%s charset is %s", filename, charset)
        # if the file contains \usepackage[xxx]{inputenc}
        # we do nothing (assuming xxx == charset)
        inputenc = re.compile(r"^[^%]*\\usepackage\[[^]]+\]{inputenc}")
        match = None
        with open(filename, encoding=charset) as src:
            for line in src:
                match = re.match(inputenc, line)
                if match is not None:
                    break

        if match is not None:
            TASK_LOGGER.debug("%s has %s", filename, match.group(0))

        else:
            # let's re-code the file
            original_file = filename + "." + charset
            os.rename(filename, original_file)
            subprocess.run(
                args=[
                    "iconv",
                    "-f",
                    charset,
                    "-t",
                    "utf-8",
                    "-o",
                    filename,
                    original_file,
                ],
                check=True,
            )
            TASK_LOGGER.info("%s recoded from %s to utf-8", filename, charset)

        # TODO: error management


def n010_remove_U202C(filename):  # NOQA N802
    """Remove all occurrences of char U202C (‬) POP DIRECTIONAL FORMATTING

    which is generally not displayed in any way.
    """
    result = subprocess.run(
        args=[
            "grep",
            "-q",
            "‬",  # tra gli apici c'è un U202C (\xE2 \x80 \xAC)
            filename,
        ],
        check=False,
    )
    # grep called from bash works also like this:
    # grep $'\xe2\x80\xac' Paper.tex
    # but I think it relies on korn-escapes

    if result.returncode == 0:
        # found something
        TASK_LOGGER.debug("found U202C in %s", filename)

        backup = filename + ".U202C_bkup"
        shutil.copy(filename, backup)

        try:
            subprocess.run(
                args=["sed", "-i", "s/‬//g", filename],  # il search patter è U202C
                check=True,
            )
        except Exception as error:
            TASK_LOGGER.warning(
                "Could not remove char U202C from %s (error: %s). Compilation might fail.",
                filename,
                error,
            )
        else:
            if os.stat(backup).st_size == os.stat(filename).st_size:
                TASK_LOGGER.error(
                    "Size of %s before and after U202C removal si the same.", filename
                )
                # raise something?

            TASK_LOGGER.info("Removed all occurrences of U202C from %s.", filename)

    else:
        # file is clean, nothing to do
        TASK_LOGGER.debug("No U202C char in %s", filename)
