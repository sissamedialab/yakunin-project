"Test the function has_documentclass"
# keep in a separate module, because test patterns are messy

import os
import tempfile

import pytest

from yakunin.lib import has_documentclass

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
    "genera un file di prova a partire da un pattern"
    pattern, result = request.param
    name = tempfile.mkstemp()[1]
    with open(name, "w") as test_file:
        test_file.write(pattern)
        test_file.flush()
        yield (name, result)
    os.unlink(name)


def test_documentclass(prove):
    "check if has_documentclass works"
    name, result = prove
    assert has_documentclass(name) is result
