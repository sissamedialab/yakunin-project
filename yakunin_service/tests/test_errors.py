"""Test the error reporting machinery."""

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
import requests

from yakunin_service.utils import PORT


@pytest.mark.parametrize(
    ("bad_fragment", "log_lines"),
    [
        ("", ["ERROR Unknown mime type"]),
        ("just text (i.e. not latex)", ["ERROR Unknown archive format text/plain"]),
        (
            r"""\documentclass{article}
\begin{document}

% Errore 2: Uso di un carattere speciale con categoria errata senza escape
L'uso di # e _ fuori contesto qui manderà in confusione l'allineamento.

% Errore 3: Chiusura di un gruppo mai aperto con parentesi graffe invertite
}

% Errore 4: Comando matematico fuori dall'ambiente math, ma con macro illegale
\text{Questo fallirà perché non ho caricato amsmath} \alpha

% Errore 1: Definizione ricorsiva infinita (Loop di espansione)
\def\parola{\parola di troppo}
\parola

\end{document}
""",
            [
                "DEBUG Archive mime type: text/x-tex",
                "DEBUG ready to compile test.tex",
                "returned non-zero exit status",
                "WARNING TeX capacity exceeded. Please check if you have a recursive definition",
                "ERROR No pdf file produced! Compilation failed.",
                "ERROR PDF generation failed",
                "ERROR Watermarking failed because of missing pdf",
            ],
        ),
    ],
)
def test_send_bad_tex(
    yakunin_service: Callable,
    tmp_path: Path,
    bad_fragment: str,
    log_lines: list[str],
):
    """Send a bad tex and get back a tar.gz with a task-log."""
    url = f"http://localhost:{PORT}/watermark/"
    tex_filepath = tmp_path / "test.tex"
    tex_filepath.write_text(data=bad_fragment)
    with tex_filepath.open(mode="rb") as in_fhandle:
        response = requests.post(
            url,
            files={"file": in_fhandle},
            timeout=11,
        )
    assert response.status_code == 200
    out_fname = tmp_path / "x.tar.gz"
    out_fname.write_bytes(response.content)
    subprocess.run(
        args=("tar", "xf", out_fname, "-C", tmp_path),
        check=True,
    )
    assert "yakunin-task.log" in [p.name for p in tmp_path.glob("*.*")]
    log_content = (tmp_path / "yakunin-task.log").read_text()
    for line in log_lines:
        assert line in log_content

    # to see the logs: from pprint import pprint
    # to see the logs: pprint(log_content)
    # to see the logs: pprint((tmp_path / "work" / "test.stdout").read_text())
    # to see the logs: assert False
