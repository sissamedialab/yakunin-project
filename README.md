# Yakunin (役人)

NB: original code was under svn at https://auriol.medialab.sissa.it/svn/misc/yakunin-project/with-script


A compilation script for wj journals.

Yakunin should receive the submitted archives (tar.gz, zip, but also
simple tex or pdf files) and perform the required task.

Possible tasks are:
- find the tex master file in the archive
- compile and produce a pdf
- watermark
- do pitstop validation
- do PDF/A transformation

Usually the result is a tar.gz archive, saved on the file system. This
archive contains the compiled pdf, the original archive and the
intermediate files (aux, etc.).

Anotherd archive for use by the typesetter can also be present.

# Installation

```sh
pip install yakunin
yakunin -h
yakunin --verify-env
```


# Tests

At the moment, tests are kept outside of the yakunin, package For a
different approach, see
<https://python-packaging.readthedocs.io/en/latest/testing.html>

# Examples

## CLI

```sh
yakunin watermark --text CIAONE -x 10 -y 500 tests/test-files/01-test.tex
```

## Programmatic

```python
import yakunin
archive = yakunin.Archive(archive=file_path)
archive.watermark(text="Ciaone")
targz_with_processed_files = archive.submission_archive()
```
