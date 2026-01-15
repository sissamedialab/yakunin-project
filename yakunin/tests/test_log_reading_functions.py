"""Test log-reading/error-reporting functions."""

import io
from pathlib import Path

import pytest

from yakunin import log_reading_lib
from yakunin.utils import TaskLogger

# Here is a list of triplets:
# function name  ---   tex log text  ---   expected output (in task log)
# use "None" if the 'tex log text" is ok with respect to "function name"
UCS_LINES = [
    #
    #
    # Undefined control sequences
    #
    ("undefined_control_sequence", "Nothing to report\n", None),
    (
        "undefined_control_sequence",
        r"""(/usr/local/texlive/2016/texmf-dist/tex/generic/oberdiek/gettitlestring.sty))
! Undefined control sequence.
\maketitle ...0} \noindent {\small \sc \@fpheader
                                                  } \afterLogoSpace \if !\@s...
l.86 \maketitle

(/usr/local/texlive/2016/texmf-dist/tex/latex/base/t1cmss.fd)
""",
        'ERROR "\\@fpheader" is undefined. Please check FAQ-123.\n',
    ),
    (
        "undefined_control_sequence",
        r"""   Changed files, or newly in use since previous run(s):
      '141908-56076.aux'
Latexmk: Maximum runs of pdflatex reached without getting stable files
Latexmk: Did not finish processing file '141908-56076.tex':
   'pdflatex' needed too many passes
Latexmk: Use the -f option to force complete processing,
""",
        None,
    ),
    #
    #
    # Latexmk max runs exceeded
    #
    ("max_runs", "Nothing to report\n", None),
    (
        "max_runs",
        r"""(/usr/local/texlive/2016/texmf-dist/tex/generic/oberdiek/gettitlestring.sty))
! Undefined control sequence.
\maketitle ...0} \noindent {\small \sc \@fpheader
                                                  } \afterLogoSpace \if !\@s...
l.86 \maketitle

(/usr/local/texlive/2016/texmf-dist/tex/latex/base/t1cmss.fd)
""",
        None,
    ),
    (
        "max_runs",
        r"""   Changed files, or newly in use since previous run(s):
      '141908-56076.aux'
Latexmk: Maximum runs of pdflatex reached without getting stable files
Latexmk: Did not finish processing file '141908-56076.tex':
   'pdflatex' needed too many passes
Latexmk: Use the -f option to force complete processing,
""",
        "WARNING Latexmk: Maximum runs of pdflatex reached without getting stable files\n",
    ),
    #
    #
    # Boldface in math mode
    #
    (
        "bf_in_math_mode",
        r"""! LaTeX Error: Command \bfseries invalid in math mode.

See the LaTeX manual or LaTeX Companion for explanation.
Type  H <return>  for immediate help.
 ...

l.124 ...repetition rate asked for by $\cite{ref3}
                                                  $, the flash ...
""",
        'WARNING Probably a "\\cite" inside mathematics. Please check line 124. Please see FAQ-123.\n',
    ),
    ("bf_in_math_mode", "Nothing to report\n", None),
    # mi aspetto di trovare il numero della linea problematica
    # 6 righe di log sotto il messaggio d'errore
    (
        "bf_in_math_mode",
        "! LaTeX Error: Command \\bfseries invalid in math mode.\n",
        "WARNING Could not understand boldface-in-math-mode error.\n",
    ),
    #
    #
    # Unicode char not setup (inputenc error)
    #
    ("inputenc_unicode_not_setup", "Nothing to report\n", None),
    (
        "inputenc_unicode_not_setup",
        r"""! Package inputenc Error: Unicode character ¦ (U+00A6)
(inputenc)                not set up for use with LaTeX.

See the inputenc package documentation for explanation.
Type  H <return>  for immediate help.
 ...

l.27 \begin{document}

You may provide a definition with
\DeclareUnicodeCharacter

""",
        "WARNING There is a unicode char that latex does not know how to handle."
        " The char is U+00A6. Please check line 27. Please see FAQ-123.\n",
    ),
    (
        "inputenc_unicode_not_setup",
        "! Package inputenc Error: Unicode character ¦ (U+00A6)\n",
        "WARNING Could not understand unicode-not-setup error.\n",
    ),
    #
    #
    # File not found
    #
    ("file_not_found", "Nothing to report\n", None),
    (
        "file_not_found",
        r"""! LaTeX Error: File `FDiagnis3' not found.

See the LaTeX manual or LaTeX Companion for explanation.
Type  H <return>  for immediate help.
 ...

l.1556 ...graphics[width=1\columnwidth]{FDiagnis3}
                                                  %
I could not locate the file with any of these extensions:
.pdf,.png,.jpg,.mps,.jpeg,.jbig2,.jb2,.PDF,.PNG,.JPG,.JPEG,.JBIG2,.JB2,.eps
Try typing  <return>  to proceed.
""",
        'WARNING You probably forgot to include "FDiagnis3" in the submitted archive.'
        " Please check line 1556. Please see FAQ-123.\n",
    ),
    (
        "file_not_found",
        "! LaTeX Error: File `FDiagnis3' not found.\n",
        "WARNING Could not understand file-not-found error.\n",
    ),
]


def make_fake_tex_log(src):
    """
    Prepare and return a file-like object containing the given "src" text.

    This "file" will mimick the tex log/stdout
    """
    fake_tex_log = io.StringIO()
    fake_tex_log.write(src)
    fake_tex_log.flush()
    fake_tex_log.seek(0)
    return fake_tex_log


# doesn not work in mark.parametrize
# (pytest's test collection complains about stringIo not having len)
# UCS_LINES = [make_fake_tex_log(x[0]) for x in UCS_LINES]  # noqa: ERA001


@pytest.mark.parametrize(("func_name", "tex_log_text", "expected"), UCS_LINES)
def test_log_reading_functions(
    func_name,
    tex_log_text,
    expected,
    setup_config,
    tmp_path: Path,
):
    """
    Call the log-reading function on a fake tex Log.

    Check that the function emits the expected message
    """
    # Ensure that the task logger writes to a file in our temp path:
    task_logger = TaskLogger(tmp_path)

    # read the fake log line by line and call the function if the
    # error line has been found
    tex_log = make_fake_tex_log(tex_log_text)
    func = getattr(log_reading_lib, func_name)
    print(f"{func=}")
    for line in tex_log:
        if line.find(func.search_string) > -1:
            func(line, tex_log, task_logger)

    log_lines = task_logger.log_file.read_text()
    if expected is not None:
        assert expected in log_lines
