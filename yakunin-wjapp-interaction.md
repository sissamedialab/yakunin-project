# yakunin (and its interaction with wjapp)

NB: work in progress - some parts are not yet implemented;
the general behavior should stay the same, but details may vary


## Intro

yakunin is a script that can perform multiple tasks.

Once the task is done, yakunin returns a tar.gz archive containing the
files generated during the task and a task "log".
Actually, yakunin prints the path of the tar.gz, it does not return it.

Examples:

 .  latex compilation: with or without specifying the tex master:

    yakunin compile x.tex
    yakunin compile --tex-master=x.tex x.zip

 .  apply a watermark onto a pdf:

    yakunin watermark x.pdf --watermark="Some text"

 .  generation of PDF/A-2b file; the given archive will be extracted,
 the tex master found and compiled, a watermark will be applied and
 the result will be transformed into PDF/A-2b:

    yakunin topdfa x.zip --watermark="Some text"


## Details

### Installation

yakunin is a python package and can be installed via pip. E.g.:

    python3 -m venv .v
    . ./.v/bin/activate
    pip install svn+https://auriol/svn/misc/yakunin-project/with-script#yakunin

    yakunin -h

The results of yakunin tasks are saved locally, so yakunin must reside
on the same machine as wjapp.


### Configuration

yakunin reads a configuration file (especially for the logging
part). A default one is installed into <sys.prefix>/etc/yakunin.json
Use `--config-file` to specify a different one.


### Important options

The tex master and the tex engine to use are often difficult to guess
correctly. So wjapp should present the user with the possibility to
indicate these during submission. The values can be passed to yakunin
through the relative options `--tex-master` and `--tex-engine`. See
details in `yakunin -h`.


### LaTeX distro

At the moment, yakunin uses the binaries (namely "latex" and "file")
that it finds in the PATH.

The functionality provided by "discriminator" (i.e. change that PATH
based on the relation between some given option and some
known/hardcoded info) could be included.


### Tasks

Most of the tasks are interrelated, so that one task can call others.

For instance, `topdfa` and `watermark` will call `mkpdf` if they have
been given a tex file (instead of a pdf file).

Also, most tasks (such as `mkpdf`) will call `watermark` if the
`--watermark` option has been used.

Internally, tasks are executed only if needed, so circular
dependencies are avoided.


#### mkpdf

    yakunin mkpdf FILE

If the given FILE is docx or odt, these are transformed into PDF
files. Otherwise FILE is treated as a tex file/archive and compilation
is attempted (see `compile`).


#### compile

    yakunin compile FILE

The only mandatory argument is a FILE to compile (any of tex, tex.gz,
tar, tar.gz, tar.bz2, zip).

Optional arguments are as follows; if they are not given, then they
are heuristically determined or defaults values are used.

`--tex-master` must be a file with path relative to the extracted
archive

`--tex-engine` one of pdflatex, latex, pdftex, tex, xelatex


#### watermark

    yakunin watermark FILE --watermark="Some text"

If the given FILE is a pdf (application/pdf), then the watermark is
simply applied to all pages.

If the given FILE is not a pdf, the generation of a pdf is first
attempted (see `mkpdf`).


#### pitstopfix

Uses Enfocus Pitstop Server on medusa to "fix-and-validate" the given
pdf file. Calls `mkpdf` and `watermark` if necessary.


#### topdfa

Uses Callas Pdftoolbox on medusa to transform the given pdf file into
PDF/A-2b. Calls `mkpdf` and `watermark` if necessary.


#### jhep

This task concatenates `mkpdf`, `watermark`, `pitstopfix` and
`topdfa`. Here the `--watermark` option is mandatory.
