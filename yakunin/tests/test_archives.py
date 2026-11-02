"""Test that all archives in test-files get compiled."""

import io
import os
import tarfile
import zipfile
from pathlib import Path

import pytest

from yakunin.archive import Archive
from yakunin.utils import aruspica_mime

from .conftest import ARCHIVES_DESC, ARCHIVES_DIR

# TODO: archives with file size = 0 byte
# TODO: archives with illegal file names
# TODO: pstriks / dvi
# TODO: tex / pdftex (instead of latex / pdflatex)
# TODO: xelatex


@pytest.mark.parametrize("archive", ARCHIVES_DESC)
def test_compilation(archive_compilation_tester, archive, setup_config):
    """
    Test the compilation of the chosen archives.

    Read the file tests/test_files/expected_results.xml and test
    archives accordig to specifications found in the file.

    """
    archive_compilation_tester(archive)


KNOWN_FORMATS = [
    ("01-test.tex", "text/x-tex"),
    ("02-test.tex.gz", "application/gzip"),  # actually wrong...
    ("03-test.zip", "application/zip"),
    ("04-test.tar.gz", "application/x-compressed-tar"),
    ("05-test.tar.bz2", "application/x-bzip-compressed-tar"),
    ("06-test.tgz", "application/x-compressed-tar"),
    ("07-test-tgz", "application/x-compressed-tar"),
    ("08-test-zip", "application/zip"),
    ("09-test-texgz", "application/gzip"),
    ("10-test-tex", "text/x-tex"),
    ("11-test.tex.bz2", "application/x-bzip2"),
    ("12-test-tex-bz2", "application/x-bzip2"),
    ("13-test-tar-bz2", "application/x-bzip-compressed-tar"),
    ("14-test.pdf", "application/pdf"),
    ("15-test.pdf.gz", "application/gzip"),
    ("16-test.pdf.bzip2", "application/x-bzip2"),
    ("17-test-pdf-gz", "application/gzip"),
    ("18-test-pdf-bzip2", "application/x-bzip2"),
    ("19-test.tar", "application/x-tar"),
    ("20-test-tar", "application/x-tar"),
    ("21-test.odt", "application/vnd.oasis.opendocument.text"),
    (
        "22-test.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    ("30456-Paper.rar", "application/vnd.rar"),
]
KNOWN_FORMATS = [(os.path.join(ARCHIVES_DIR, x[0]), x[1]) for x in KNOWN_FORMATS]


@pytest.mark.parametrize(("archive", "mime"), KNOWN_FORMATS)
def test_filetype_guessing(archive, mime, setup_config):
    """Verify the guessing of the mime type of certain files."""
    found_mime = aruspica_mime(archive)
    # different systems can give slightly different answers for RAR archives
    # (e.g. my machine and gitlab-ci 😢)
    if "x-rar" in mime:
        assert found_mime in {"application/vnd.rar", "application/x-rar"}
    else:
        assert found_mime == mime


TEX_MASTERS = [
    ("01-test.tex", "01-test.tex"),
    ("02-test.tex.gz", "02-test.tex"),
    ("03-test.zip", "test.tex"),
    ("04-test.tar.gz", "test.tex"),
    ("05-test.tar.bz2", "test.tex"),
    ("30437-Generative_adversarial_networks.zip", "main.tex"),
]
TEX_MASTERS = [(os.path.join(ARCHIVES_DIR, x[0]), x[1]) for x in TEX_MASTERS]


@pytest.mark.parametrize(("archive", "master"), TEX_MASTERS)
def test_tex_master_guessing(archive, master):
    """Verify the guessing of the tex master for certain archives."""
    with Archive(archive=archive) as arc:
        arc.find_master()
        assert arc.tex_master.name == master


def test_zip_slip(tmp_path, caplog) -> None:
    """
    Test that zips containing path traversal entries are rejected.

    Note that Archive uses shutils.unpack_archive(),
    that silently ignores any path
    that contains ".."
    or that starts with "/".
    """
    evil_paths = [
        "../../evil__two-up.txt",
        "../evil__one-up.txt",
        "aa/bb/../../../evil__two-down-three-up.txt",
        "/evil__root.txt",
        "/tmp/evil__tmp.txt",  # noqa: S108
    ]

    zip_path = tmp_path / "x.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("good.txt", "good payload")
        for evil_path in evil_paths:
            zf.writestr(evil_path, "zip slip payload")

    a = Archive(archive=zip_path)
    extracted_files = [f.name for f in a.work_dir.iterdir()]
    assert len(extracted_files) == 1
    assert "good.txt" in extracted_files

    for evil_path in evil_paths:
        assert not (a.work_dir / evil_path).resolve().exists()

    assert a.can_continue is True


def _add_member(tf: tarfile.TarFile, name: str, payload: bytes = b"payload", **attrs) -> None:
    """Add a member to tf; attrs (type, linkname, mode, ...) are set on the TarInfo."""
    info = tarfile.TarInfo(name)
    info.size = len(payload) if attrs.get("type", tarfile.REGTYPE) == tarfile.REGTYPE else 0
    for key, value in attrs.items():
        setattr(info, key, value)
    tf.addfile(info, io.BytesIO(payload) if info.size else None)


EVIL_TAR_MEMBERS = {
    "one-up": [{"name": "../evil__one-up.txt"}],
    "two-down-three-up": [{"name": "aa/bb/../../../evil__two-down-three-up.txt"}],
    "absolute": [{"name": "/tmp/evil__tmp.txt"}],  # noqa: S108
    "symlink-absolute": [{"name": "passwd", "type": tarfile.SYMTYPE, "linkname": "/etc/passwd"}],
    "symlink-up": [{"name": "up", "type": tarfile.SYMTYPE, "linkname": "../.."}],
    "write-through-symlink": [
        {"name": "dir", "type": tarfile.SYMTYPE, "linkname": ".."},
        {"name": "dir/evil__through-symlink.txt"},
    ],
    "hardlink-outside": [{"name": "shadow", "type": tarfile.LNKTYPE, "linkname": "/etc/passwd"}],
    "device": [{"name": "evil__dev", "type": tarfile.CHRTYPE, "devmajor": 1, "devminor": 3}],
}


@pytest.mark.parametrize("compression", ["", "gz", "bz2"])
@pytest.mark.parametrize("case", EVIL_TAR_MEMBERS)
def test_tar_slip(tmp_path, case, compression) -> None:
    """Test that tars with path traversal / dangerous links are rejected (tarfile "data" filter)."""
    tar_path = tmp_path / "upload" / f"x.tar.{compression}" if compression else tmp_path / "upload" / "x.tar"
    tar_path.parent.mkdir()
    with tarfile.open(tar_path, f"w:{compression}") as tf:
        _add_member(tf, "good.tex", b"\\documentclass{article}")
        for member in EVIL_TAR_MEMBERS[case]:
            _add_member(tf, **member)

    a = Archive(archive=tar_path)

    # "data" filter strips leading "/" from absolute names: extracted (harmlessly) inside work_dir
    assert a.can_continue is (case == "absolute")
    for path in a.temp_dir.rglob("evil__*"):
        # only acceptable if inside work_dir (it shouldn't, but it would be harmless)
        assert a.work_dir in path.parents, f"{path} written outside work_dir"
    assert not (a.work_dir / "passwd").exists()
    assert not (a.work_dir / "shadow").exists()
    assert not (a.work_dir / "up").exists()
    assert not list(tmp_path.glob("evil__*"))
    assert not Path("/tmp/evil__tmp.txt").exists()  # noqa: S108


def test_tar_safe_links_are_kept(tmp_path) -> None:
    """Test that the "data" filter still allows links that stay inside the archive."""
    tar_path = tmp_path / "x.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        _add_member(tf, "sub/real.tex", b"real")
        _add_member(tf, "alias.tex", type=tarfile.SYMTYPE, linkname="sub/real.tex")
        _add_member(tf, "hard.tex", type=tarfile.LNKTYPE, linkname="sub/real.tex")

    a = Archive(archive=tar_path)

    assert a.can_continue is True
    assert (a.work_dir / "alias.tex").is_symlink()
    assert (a.work_dir / "alias.tex").read_bytes() == b"real"
    assert (a.work_dir / "hard.tex").read_bytes() == b"real"
