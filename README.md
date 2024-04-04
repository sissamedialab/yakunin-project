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
python3 -m venv v . ./v/bin/activate
# Optional: pip install wheel
pip install svn+http://auriol/svn/misc/yakunin-project/with-script#yakunin
yakunin -h
```

Once installed, the script can also be called from its installation dir
(it will find its own python automagically)
`/path/to/virtual-env/bin/yakunin -h`

# Development environment

```sh
svn co <http://auriol/svn/misc/yakunin-project/with-script>
yakunin-project cd yakunin-project

python3 -m venv v . v/bin/activate pip install -U pip

python setup.py install yakunin -h

pip install pytest pytest
```

# Tests

At the moment, tests are kept outside of the yakunin, package For a
different approach, see
<https://python-packaging.readthedocs.io/en/latest/testing.html>

# Examples

```sh
# Send a slow-compiling file followed by three fast ones
export url=http://localhost:8888/compile
export common="-F <file=@vari>/arch.zip -F engine=lualatex"

curl $common -F master=slow.tex $url & sleep 1
curl $common -F master=fast.tex $url &
curl $common -F master=fast.tex $url &
curl $common -F master=fast.tex $url &
```
