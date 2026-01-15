"""Test the function has_documentclass."""
# keep in a separate module, because test patterns are messy

import tempfile
from pathlib import Path

import pytest

from yakunin.utils import has_documentclass

OK_PATTERNS = [
    # simple, real file
    r"""\documentclass{article}
\usepackage{datetime}
\begin{document}
TEST \today \currenttime
\end{document}
""",
    # spaces before \documentclass
    r"""   \documentclass{article}
\begin{document}
hi
\end{document}
""",
    # some blank lines
    r"""


\documentclass{article}
\usepackage{datetime}
\begin{document}
TEST \today \currenttime
\end{document}
""",
]


FAIL_PATTERNS = [
    # no documentclass
    "ciao\nbel\n",
    # comments before documentclass
    r"""%\documentclass{article}
\section{Intro}
hi
""",
]


PATTERNS = [(x, True) for x in OK_PATTERNS]
PATTERNS.extend([(x, False) for x in FAIL_PATTERNS])


@pytest.fixture(params=PATTERNS)
def prove(request):
    """
    Genera un file di prova a partire da un pattern.

    Yields:
      tuple(str, str): file name and results. Unlink the file on teardown.

    """
    pattern, result = request.param
    test_file = Path(tempfile.mkstemp()[1])
    test_file.write_text(pattern, encoding="utf-8")
    yield (test_file.absolute(), result)
    test_file.unlink()


def test_documentclass(prove):
    """Check if has_documentclass works."""
    name, result = prove
    assert has_documentclass(name) is result
