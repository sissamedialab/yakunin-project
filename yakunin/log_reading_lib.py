"""These functions can interpret errors reported in tex log files.

They can also report an author-frindly explanation of the error.

Each function deals with only one type of error.

The error can be identified in the log (spefically, latexmk
stdout/stderr) by the function's "search_string".

Each function is passed a line of the log file where the search string
has been found. Also, the file_handle beeing read is passed to the
function. This is so that the function can consume more lines of the
log if it needs to find additinal info. For instance, "undefined
controlo sequences" are displayed in the log two lines after the error
message.

Each function in this module will be "called" by
yakunin.Archive::read_log durin log analysis.
"""

import logging
import re

TASK_LOGGER = logging.getLogger("yakunin.task")
LINE_NUMBER_P = re.compile(r"^l\.([0-9]+) ")
UNICODE_CHAR_P = re.compile(r"\((U\+[A-F0-9]{4,4})\)")
FILE_NOT_FOUND_P = re.compile(r"^! LaTeX Error: File `([^']+)' not found.")


def report_error_and_line(
    file_handle,
    text_for_the_warning,
    text_for_reporting_issues_while_reading_log,
    faq=None,
):
    """Read the tex log.

    Read the log (file_handle) until a line number has been found.
    Then report the given warning (TASK_LOGGER.warning).  If there was
    a problem while looking for the line number, report the other
    given text.

    """
    line_number = None
    file_position = file_handle.tell()
    try:
        # look for the line of the log file
        # that contains the line number of the error
        line = file_handle.readline()
        while line:
            match = re.match(LINE_NUMBER_P, line)
            if match:
                line_number = match.group(1)
                msg = text_for_the_warning
                msg += f" Please check line {line_number}."
                if faq is not None:
                    msg += " " + str(faq)
                TASK_LOGGER.warning(msg)
                break
            line = file_handle.readline()
        assert line_number is not None

    except Exception as error:
        # if anything funny happens,
        # report a warning,
        # seek file_handle to its original position
        # and return
        file_handle.seek(file_position)
        TASK_LOGGER.warning(text_for_reporting_issues_while_reading_log)
        TASK_LOGGER.debug(error)


def expose(search_string=None):
    "Decorate a function so that it is used by read_log"

    def wrapper(func):
        func.exposed = True
        func.search_string = search_string
        return func

    return wrapper


@expose(search_string="Undefined control sequence")
def undefined_control_sequence(line, file_handle):
    'How to read and what to do upon "Undefined control sequence" errors'
    # TODO: move to decorator?
    # NB: "__name__" inside a function returns the module's name
    TASK_LOGGER.debug('Function "%s" called on "%s"', __name__, line.strip())

    next_line = file_handle.readline()
    pesky_cs = next_line.strip().split(" ")[-1]
    TASK_LOGGER.error('"%s" is undefined. Please check FAQ-123.', pesky_cs)


@expose(
    search_string="Latexmk: Maximum runs of pdflatex reached without getting stable files"
)
def max_runs(line, file_handle):
    "Look for latexmk's maximum-runs error"
    TASK_LOGGER.warning(line.strip())


@expose(search_string=r"! LaTeX Error: Command \bfseries invalid in math mode.")
def bf_in_math_mode(line, file_handle):
    r"! LaTeX Error: Command \bfseries invalid in math mode."
    # ! LaTeX Error: Command \bfseries invalid in math mode.
    #
    # See the LaTeX manual or LaTeX Companion for explanation.
    # Type  H <return>  for immediate help.
    #  ...
    #
    # l.124 ...repetition rate asked for by $\cite{ref3}
    #                                                   $, the flash ...
    #

    report_error_and_line(
        file_handle,
        r'Probably a "\cite" inside mathematics.',
        "Could not understand boldface-in-math-mode error.",
        faq="Please see FAQ-123.",
    )


@expose(search_string="! Package inputenc Error: Unicode character")
def inputenc_unicode_not_setup(line, file_handle):
    "! Package inputenc Error: Unicode character ¦ (U+00A6)"
    # ! Package inputenc Error: Unicode character ¦ (U+00A6)
    # (inputenc)                not set up for use with LaTeX.

    # See the inputenc package documentation for explanation.
    # Type  H <return>  for immediate help.
    #  ...

    # l.27 \begin{document}

    # You may provide a definition with
    # \DeclareUnicodeCharacter

    char = re.search(UNICODE_CHAR_P, line)
    char = char.group(1)
    TASK_LOGGER.debug("Not-setup unicode char: %s", char)

    text_for_the_warning = (
        "There is a unicode char that latex does not know how to handle. "
        f"The char is {char}."
    )
    text_for_reporting_issues_while_reading_log = (
        "Could not understand unicode-not-setup error."
    )
    faq = "Please see FAQ-123."

    report_error_and_line(
        file_handle,
        text_for_the_warning,
        text_for_reporting_issues_while_reading_log,
        faq=faq,
    )


# TODO: use search_regexp?
@expose(search_string="! LaTeX Error: File ")
def file_not_found(line, file_handle):
    "! LaTeX Error: File `FDiagnis3' not found."
    # ! LaTeX Error: File `FDiagnis3' not found.

    # See the LaTeX manual or LaTeX Companion for explanation.
    # Type  H <return>  for immediate help.
    #  ...

    # l.1556 ...graphics[width=1\columnwidth]{FDiagnis3}
    #                                                   %
    # I could not locate the file with any of these extensions:
    # .pdf,.png,.jpg,.mps,.jpeg,.jbig2,.jb2,.PDF,.PNG,.JPG,.JPEG,.JBIG2,.JB2,.eps
    # Try typing  <return>  to proceed.

    missing_file = re.match(FILE_NOT_FOUND_P, line)
    missing_file = missing_file.group(1)

    report_error_and_line(
        file_handle,
        f'You probably forgot to include "{missing_file}" in the submitted archive.',
        "Could not understand file-not-found error.",
        faq="Please see FAQ-123.",
    )


# TODO: use search_regexp?
@expose(search_string="Package biblatex Warning: File ")
def bbl_wrong_version(line, file_handle):
    "Package biblatex Warning: File xxx is wrong format version"
    if "is wrong format version" in line:
        TASK_LOGGER.warning(
            "bbl version mismatch. This can lead to errors. " "Please see FAQ-123"
        )
