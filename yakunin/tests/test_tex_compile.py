"""Test the options that tex_compile passes to latexmk (wjs/specs#2681)."""

import subprocess
import zipfile

import pytest

from yakunin.archive import Archive

CITING_TEX = r"""\documentclass{article}
\begin{document}
Hello \cite{knuth}.
\bibliographystyle{plain}
\bibliography{refs}
\end{document}
"""

# bibtex fails on repeated entries (exit status 1 → latexmk "Bibtex errors")
BROKEN_BIB = r"""@book{knuth, author={Knuth, D. E.}, title={The {\TeX}book}, publisher={AW}, year=1984}
@book{knuth, author={Knuth, D. E.}, title={The {\TeX}book}, publisher={AW}, year=1984}
"""

GOOD_BBL = r"""\begin{thebibliography}{1}
\bibitem{knuth} D.~E. Knuth. \newblock {\em The {\TeX}book}. \newblock AW, 1984.
\end{thebibliography}
"""


def _make_zip(tmp_path, members: dict[str, str]):
    zip_path = tmp_path / "upload.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return zip_path


def _undefined_citations(arc: Archive) -> int:
    """Count the undefined citations in the .log of the last pdflatex run."""
    log = arc.tex_master.with_suffix(".log").read_text(encoding="utf-8", errors="replace")
    return log.count("Citation `knuth' on page 1 undefined")


@pytest.fixture
def captured_args(monkeypatch):
    """Do not really run latexmk: just record the command line."""
    calls = []
    real_run = subprocess.run

    def fake_run(args, **kwargs):
        if args[0] != "latexmk":
            # e.g. "file" used to guess the mime type
            return real_run(args, **kwargs)
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=b"")

    monkeypatch.setattr("yakunin.archive.subprocess.run", fake_run)
    return calls


@pytest.mark.parametrize("with_bbl", [True, False])
def test_latexmk_options(tmp_path, captured_args, with_bbl):
    """-norc and -f are always given; -bibtex- only when the author provided <master>.bbl."""
    members = {"paper.tex": CITING_TEX, "refs.bib": BROKEN_BIB}
    if with_bbl:
        members["paper.bbl"] = GOOD_BBL
    with Archive(archive=_make_zip(tmp_path, members)) as arc:
        arc.tex_compile()

    assert len(captured_args) == 1
    args = captured_args[0]
    assert args[0] == "latexmk"
    assert "-norc" in args
    assert "-f" in args
    assert ("-bibtex-" in args) is with_bbl
    assert args[-1] == "paper.tex"


def test_bbl_of_other_name_is_ignored(tmp_path, captured_args):
    """Only <master>.bbl disables bibtex (e.g. an "output.bbl" does not)."""
    members = {"paper.tex": CITING_TEX, "refs.bib": BROKEN_BIB, "output.bbl": GOOD_BBL}
    with Archive(archive=_make_zip(tmp_path, members)) as arc:
        arc.tex_compile()
    assert len(captured_args) == 1
    assert "-bibtex-" not in captured_args[0]


def test_latexmkrc_is_not_executed(tmp_path):
    """A latexmkrc in the submitted archive must not be executed."""
    marker = tmp_path / "pwned"
    rc = f"open(my $fh, '>', '{marker}'); close($fh);\n"
    members = {"paper.tex": CITING_TEX, "refs.bib": BROKEN_BIB, ".latexmkrc": rc, "latexmkrc": rc}
    with Archive(archive=_make_zip(tmp_path, members)) as arc:
        arc.tex_compile(timeout_compilation=120)
    assert not marker.exists()


def test_author_bbl_is_used(tmp_path):
    """With the author's .bbl, a broken .bib does not matter: clean compilation, citations resolved."""
    members = {"paper.tex": CITING_TEX, "refs.bib": BROKEN_BIB, "paper.bbl": GOOD_BBL}
    with Archive(archive=_make_zip(tmp_path, members)) as arc:
        arc.tex_compile(timeout_compilation=120)
        log_lines = arc.task_logger.log_file.read_text(encoding="utf-8").splitlines()
        assert "INFO Successfully compiled paper.tex" in log_lines
        assert arc.main_pdf == "paper.pdf"
        assert (arc.temp_dir / "paper.pdf").exists()
        assert _undefined_citations(arc) == 0
        # the author's .bbl is untouched
        assert arc.tex_master.with_suffix(".bbl").read_text(encoding="utf-8") == GOOD_BBL


def test_force_mode_runs_bibtex_after_latex_errors(tmp_path):
    """
    A pdflatex error (here: a missing figure) does not stop latexmk.

    Without -f, latexmk stops after the first pdflatex run and never runs bibtex:
    the PDF has undefined citations. With -f, bibtex runs and citations are resolved;
    latexmk still exits with non-zero status, logged as a warning.
    """
    tex = CITING_TEX.replace(
        r"\begin{document}",
        "\\usepackage{graphicx}\n\\begin{document}\n\\includegraphics{missing-figure}",
    )
    good_bib = BROKEN_BIB.splitlines()[0] + "\n"
    members = {"paper.tex": tex, "refs.bib": good_bib}
    with Archive(archive=_make_zip(tmp_path, members)) as arc:
        arc.tex_compile(timeout_compilation=120)
        log_lines = arc.task_logger.log_file.read_text(encoding="utf-8").splitlines()
        assert any(line.startswith("WARNING Command '['latexmk'") for line in log_lines)
        assert any('forgot to include "missing-figure"' in line for line in log_lines)
        assert arc.main_pdf == "paper.pdf"
        assert arc.tex_master.with_suffix(".bbl").exists()
        assert _undefined_citations(arc) == 0
