"""Extract, compile & watermark WJ TeX archives."""

import inspect
import io
import logging
import os
import pathlib
import re
import shutil
import signal
import subprocess
import tempfile
import zipfile
from pathlib import Path

import requests

from . import log_reading_lib, src_tidyup_lib
from .exceptions import (
    NoTeXMasterError,
    PDFGenerationError,
    UnknownArchiveFormatError,
)
from .utils import (
    TaskLogger,
    aruspica_mime,
    has_documentclass,
    read_pitstop_report,
    setup_yakunin,
)

app_logger = logging.getLogger("yakunin")


class Archive:
    """
    The internal representation of a submitted archive.

    An "archive" can be any of zip, tar.gz, xtar (see shutil.unpack_archive)
    but also a simple tex file or a pdf file
    (in this last case, some operations will fail).
    """

    # non-tex files that I can receive and the I can do something with
    # e.g. if I get a pdf, I can do watermark, pdf/A, etc.
    # if I get a docx or odt, I can do to-pdf, watermark, etc.
    non_tex_known_types = (
        "application/pdf",
        "application/vnd.oasis.opendocument.text",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    def __enter__(self):
        """Let Archive be used as context manager."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Clean up temp dir when leaving Archive's context."""
        if self.temp_dir and self.temp_dir.exists():
            if app_logger.getEffectiveLevel() == logging.DEBUG:
                app_logger.critical("Please remove %s", self.temp_dir)
            else:
                shutil.rmtree(self.temp_dir)

    def __init__(
        self,
        archive: str,
        tex_master: str | None = None,
        base_dir: str = "/tmp",  # noqa: S108
    ):
        """
        Initialize an Archive object.

        Unpack the received "archive" in temporary folder.
        """
        setup_yakunin()

        self.tex_master = Path(tex_master) if tex_master else None
        self.main_pdf = None

        # temp dir
        # ========
        # The folders "submission" and "work", the task log and the
        # main pdf will be created inside this dir
        self.temp_dir = Path(tempfile.mkdtemp(dir=base_dir))

        # task logger
        # ===========
        # This logger writes to a "yakunin-task.log" file in the temp_dir
        # all relevant steps of the required task. This task log
        # is meant to be used to communicate with the calling application.
        self.task_logger = TaskLogger(self.temp_dir)
        self.task_logger.debug("Working in %s on %s", self.temp_dir, archive)

        self.work_dir = self._unpack_archive(archive)

    def _unpack_archive(self, archive: str) -> Path:
        """
        Open the archive.

        Save the archive in a temporary location uncompress the
        archive (if needed).

        Edge case: if the received "archive" is a pdf, just save the
        file in a temporary location NB: some operations might fail

        Raises:
          FileNotFoundError: if the archive to process does not exist
          UnknownArchiveFormatError: if we cannot identify the archive format.
          RuntimeError: if something unexpected occurs.
          ReadError: if the archive cannot be read.

        """
        # submission dir
        # ==============
        # contains the received file
        submission_dir = self.temp_dir / "submission"
        submission_dir.mkdir(exist_ok=False)
        archive = Path(archive)
        if not archive.exists():
            raise FileNotFoundError

        archive_backup = submission_dir / archive.name
        archive_backup.write_bytes(archive.read_bytes())

        # work dir
        # ========
        # where compilation/watermarking/etc. takes place
        work_dir = self.temp_dir / "work"
        work_dir.mkdir(exist_ok=False)

        # mime type
        # =========
        mime_type = aruspica_mime(archive)
        if not mime_type:
            raise RuntimeError(f"Unknown mime type for {archive}. Is aruspica_mime() broken?")
        self.task_logger.debug("Archive mime type: %s", mime_type)

        # now that we have a mimetype, lets find a suitable format for
        # shutil.unpack_archive
        epatografo = {
            "text/x-tex": "copy",
            "application/pdf": "copy",
            "application/zip": "zip",
            "application/x-tar": "tar",
            "application/x-compressed-tar": "gztar",
            "application/x-bzip-compressed-tar": "bztar",
            "application/gzip": "gz",
            "application/x-bzip2": "bz",
            "application/x-rar": "any",
            "application/vnd.rar": "any",
            "application/vnd.oasis.opendocument.text": "copy",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "copy",
        }
        if mime_type not in epatografo:
            self.task_logger.error("Unknown archive format %s", self.mime_type)
            raise UnknownArchiveFormatError

        formato = epatografo[mime_type]

        # extract/write files
        # ===================
        # TODO: switch to patool? https://libraries.io/pypi/patool
        try:
            shutil.unpack_archive(archive_backup, work_dir, formato)
        except shutil.ReadError as exception:
            app_logger.warning(
                "Cannot unpack %s as %s: %s",
                archive_backup,
                formato,
                exception,
            )
            raise
        else:
            self.task_logger.info("Unpacked %s as %s", archive_backup, formato)

        return work_dir

    def find_master(self):
        """
        Navigate the archive and find the tex_master.

        Raises:
          NoTeXMasterError: if it cannot be found.
          RuntimeError: if there are no files in the archive.

        """
        if self.tex_master:
            self.task_logger.info("TeX master (given): %s", self.tex_master)
            return

        # General idea
        # ============

        # se c'è un solo file, ed è un file ascii di qualche tipo,
        # allora assumi che questo sia il master tex
        # (controlla che non sia un docx o un pdf?)

        # altrimenti, cerca tutti i file con estensione ".tex"
        # se non ce n'è neanche uno, metti in lista tutti i file non binari

        # se ci sono più file, cerca quelli che contengono
        # "\documentclass"; tra questi, scegli come master il file più
        # vicino alla radice (cioè quello con meno "/" nel nome)

        # se non ci sono file che contegono "\documentclass", prova
        # con "\documentstyle"

        # come ultima spiaggia, scegli il primo file non binario

        # One file only
        # =============
        files = list(self.work_dir.glob("**/*"))
        if not files:
            raise RuntimeError("No file to work with? Some error during unpack?")

        if len(files) == 1:
            mime = aruspica_mime(files[0])
            app_logger.debug("Mime of master %s is %s", files[0], mime)
            if mime in Archive.non_tex_known_types:
                self.task_logger.warning("Mime of master %s is %s. Not TeX!", files[0], mime)
                # do not set tex_master and raise an exception
                raise NoTeXMasterError
            # else, we the mime type is good
            self.tex_master = files[0]
            return

        # More files
        # ==========

        # .tex
        tex_files = list(
            filter(lambda x: x.suffix in {".tex", ".TEX"}, files),
        )

        if len(tex_files) == 1:
            self.tex_master = tex_files[0]
            self.task_logger.debug(
                "Many files, but only one .tex. Master is %s",
                self.tex_master,
            )
            return

        # many .tex
        if tex_files:
            # tieni solo quelli che contengono \documentclass
            tex_files = list(filter(has_documentclass, tex_files))
            # TODO: what if no tex has \documentclass???
            # se c'è un main.tex usa quello
            if "main.tex" in tex_files:  # FIXME!!! tex_files is a list of Paths!
                self.tex_master = "main.tex"
            else:
                # altrimenti prendi quello più vicino alla radice
                tex_files = sorted(tex_files, key=lambda x: len(x.parts))
                self.tex_master = tex_files[0]
            self.task_logger.info(
                "TeX master (found %s with \\documentclass): %s",
                len(tex_files),
                self.tex_master.name,
            )
            return

        # no .tex
        app_logger.error("WRITE ME!!!")

    def tex_compile(self, **kwargs):
        """
        Compile a tex (run tex_engine on the tex_master).

        Raises:
          RuntimeError: is the system is not correctly configured.

        """
        # TODO: read the following:
        # A Decorator-Based Build System
        # https://www.artima.com/weblogs/viewpost.jsp?thread=241209
        if not self.tex_master:
            self.find_master()
        tex_engine = kwargs.get("tex_engine", "latexmk -pv- -pdf")
        tex_options = [
            "-interaction=nonstopmode",
        ]

        timeout = kwargs.get("timeout_compilation", 13)

        if not self.tex_master or not tex_engine:
            raise RuntimeError(f"Missing either tex master ({self.tex_master}) or tex engine {tex_engine}")

        # the tex master can be inside a subdir of "work"
        # we move there and keep only the basename of the tex master
        tex_dir = self.tex_master.parent

        # correct known problems in the tex source
        self.tideup_src()

        # build the compilation command
        args = tex_engine.split()
        args.extend(tex_options)
        args.append(self.tex_master.name)

        self.task_logger.debug(
            "ready to compile %s in %s with command %s",
            self.tex_master.name,
            tex_dir,
            " ".join(args),
        )
        stdout = None
        try:
            # NB: do not use "encoding='utf-8'"
            # because pesky files have broken encodings
            result = subprocess.run(
                args=args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=timeout,
                cwd=tex_dir,
            )
        except subprocess.CalledProcessError as error:
            # Here I log a warning.
            # Later on, I will examine the situation more accurately
            # an decide whether to eventually log a blocking error
            self.task_logger.warning(error)
            # stdout/stderr can be taken from the exception
            stdout = error.stdout
        except subprocess.TimeoutExpired as error:
            self.task_logger.error("Compilation timed out after %s seconds", timeout)  # noqa: TRY400
            stdout = error.stdout
        else:
            self.task_logger.info("Successfully compiled %s", self.tex_master.name)
            stdout = result.stdout
        finally:
            # dump all stdout/stderr to basename.stdout
            if stdout is not None:
                self.tex_master.with_suffix(".stdout").write_bytes(stdout)

        # read the logs (latexmk, latex, etc.)
        # and log away problems as needed
        self.read_log()

        # move the final pdf to the "root" of the temp_dir
        self.main_pdf = self.tex_master.with_suffix(".pdf").name
        generated_pdf = tex_dir / self.main_pdf
        if generated_pdf.exists():
            generated_pdf.rename(self.temp_dir / self.main_pdf)
        else:
            self.task_logger.error("No pdf file produced! Compilation failed.")

        return self.submission_archive()

    def watermark(self, **kwargs):  # noqa: C901, PLR0914, PLR0915
        """
        Apply a watermark.

        The given watermark is applied to the given height on the
        right-hand side of the page. If the page is in landscape, the
        watermark is still applied to the long edge. It is assumed
        that the page is rotated clock-wise, so the watermark will be
        on the bottom.

        Raises:
          PDFGenerationError: if we can't get a PDF to work with.

        """
        # using same approach as https://auriol/svn/misc/watermark
        # for an alternative, see https://stackoverflow.com/a/49471012/1581629

        text = kwargs.get("text", "DRAFT")
        wm_x = kwargs.get("x", "550")
        wm_y = kwargs.get("y", "620")
        # TODO: timeout is difficult for watermark because we have many steps

        app_logger.debug('watermark requested: "%s"@(%s, %s)', text, wm_x, wm_y)

        if not self.main_pdf:
            self.mkpdf(**kwargs)

        if not self.main_pdf:
            raise PDFGenerationError("Watermarking failed because of missing pdf")

        # parenthesis must be escaped when used in postscript
        text = re.sub(r"([()])", r"\\\1", text)

        # let's work in the work dir
        pdf_file = self._move_main_pdf_to_work_dir()

        # TODO: manage explicit page selection:
        # e.g.: watermark.sh -r3east 15west 16north JCAP_040P_1216.pdf ...

        # run pdfinfo to find pg. number and rotated pages
        # (need -f / -l for rotation info, assuming pdf < 1000 pages)
        # https://stackoverflow.com/a/29647772/1581629

        # TODO use try/except
        result = subprocess.run(
            args=[
                "pdfinfo",
                "-f",
                "1",
                "-l",
                "1000",
                # '-box',  # \Mediabox & co.
                pdf_file,
            ],
            stdout=subprocess.PIPE,
            text=True,
            check=True,
            cwd=self.work_dir,
        )
        # Example output
        # Page    9 rot:  0
        # Page   10 size: 595.276 x 841.89 pts (A4)
        # Page   10 rot:  90
        # Page   11 size: 595.276 x 841.89 pts (A4)
        rotation_pattern = r"^Page *(?P<pg_num>[0-9]+) rot: *(?P<rotation>[0-9]+)$"
        pages_pattern = r"^Pages: *(?P<pg_num>[0-9]+)$"
        pages_to_rotate = {}
        # transform the rotation from the degrees read by pdfinfo
        # to the "/Orientation" needed by postscript
        # (Postscript reference, pg. 412(426))
        degrees_to_orientation = {"0": "0", "90": "3", "180": "2", "270": "1"}
        num_pages = None
        for line in io.StringIO(result.stdout):
            # read the number of pages (how long the pdf file is)
            if num_pages is None:
                match = re.match(pages_pattern, line)
                if match:
                    num_pages = int(match.group("pg_num"))
                    continue

            # check if any page is rotated
            match = re.match(rotation_pattern, line)
            if match:
                rotation = match.group("rotation")
                if rotation == "0":
                    continue
                page = match.group("pg_num")

                # prepare "orientations" for pdftk
                # if the rotation is not 90 or 270
                # report a warning but do not rotate
                # (since I've never seen anything else)
                orientation = degrees_to_orientation.get(rotation, "0")
                if orientation == "0":
                    self.task_logger.warning(
                        "Found page %s rotated by %d degrees. "
                        "Applying watermark as if there was no rotation. "
                        "Please check.",
                        page,
                        rotation,
                    )
                    continue
                pages_to_rotate[page] = orientation

        # auxiliary files
        # the watermark in a postscript file
        watermark_ps_name = Path(
            tempfile.mkstemp(
                prefix="watermark",
                suffix=".ps",
                dir=self.work_dir,
            )[1],
        )

        # the pdf watermark (generated from the ps)
        watermark_name = Path(
            tempfile.mkstemp(
                prefix="watermark",
                suffix=".pdf",
                dir=self.work_dir,
            )[1],
        )

        # the final result (the main pdf watermarked)
        watermarked_name = Path(
            tempfile.mkstemp(
                prefix=self._main_pdf_se(),
                suffix="-wm.pdf",
                dir=self.work_dir,
            )[1],
        )

        if not pages_to_rotate:
            # Prepare and apply a single watermark

            # Prepare the watermark:
            # first make a postscript file
            # (A4 portrait page with wm on the right-hand side)
            # generate the pdf from the ps
            # and finally apply it to the main pdf

            # create the postscript file
            watermark_ps_name.write_text(
                f"{wm_x} {wm_y} moveto -90 rotate 0.75 setgray /Courier findfont 30 scalefont setfont ({text}) show",
                encoding="utf-8",
            )

            # generate the pdf from the ps
            subprocess.run(
                args=[
                    "gs",
                    "-P-",
                    "-q",
                    "-dSAFER",
                    "-dNOPAUSE",
                    "-dBATCH",
                    f"-sOutputFile={watermark_name}",
                    "-sDEVICE=pdfwrite",
                    "-sPAPERSIZE=a4",
                    "-dAutoRotatePages=/None",
                    "-c",
                    "<</Orientation 0>> setpagedevice",
                    "-f",
                    watermark_ps_name,
                ],
                check=True,
                cwd=self.work_dir,
            )

            # apply the watermark
            subprocess.run(
                args=[
                    "pdftk",
                    self.main_pdf,
                    "background",
                    watermark_name,
                    "output",
                    watermarked_name,
                ],
                check=True,
                cwd=self.work_dir,
            )

        else:
            self.task_logger.debug("Rotating watermark for pages %s", pages_to_rotate)

            # create the postscript code
            # https://stackoverflow.com/a/15756108/1581629
            postscript_code = f"""%!PS- Adobe-3.0
%%Pages: {num_pages}
%%EndComments
"""
            for i in range(1, num_pages + 1):
                page_setup = "<< /Orientation 0 >> setpagedevice\n"
                if str(i) in pages_to_rotate:
                    page_setup = "<< /Orientation 3>> setpagedevice\n"

                postscript_code += f"""%%Page: {i} {i}
%%BeginPageSetup
{page_setup}
%%EndPageSetup
{wm_x} {wm_y} moveto -90 rotate 0.75 setgray
/Courier findfont 30 scalefont setfont
({text}) show
showpage
"""
            postscript_code += "%%EOF\n"

            # create the postscript file
            watermark_ps_name.write_text(postscript_code, encoding="utf-8")

            # generate the pdf from the ps
            subprocess.run(
                args=[
                    "gs",
                    "-P-",
                    "-q",
                    "-dSAFER",
                    "-dNOPAUSE",
                    "-dBATCH",
                    f"-sOutputFile={watermark_name}",
                    "-sDEVICE=pdfwrite",
                    "-sPAPERSIZE=a4",
                    "-dAutoRotatePages=/None",
                    watermark_ps_name,
                ],
                check=True,
                cwd=self.work_dir,
            )

            # apply the multibackground
            subprocess.run(
                args=[
                    "pdftk",
                    self.main_pdf,
                    "multibackground",
                    watermark_name,
                    "output",
                    watermarked_name,
                ],
                check=True,
                cwd=self.work_dir,
            )

        self.main_pdf = watermarked_name.name
        watermarked_name.rename(self.temp_dir / self.main_pdf)
        self.task_logger.debug("Watermark applied.")
        return self.submission_archive()

    def pitstop_validate(self, **kwargs):  # noqa: PLR0915
        """
        Execute Pitstop fix & validation of the given PDF file.

        Raises:
          PDFGenerationError: if we can't get a PDF to work with.
          RuntimeError: when some configuration is wrong.

        """
        app_logger.debug("Pitstop validation requested")

        text = kwargs.get("text")
        if text is not None:
            self.watermark(**kwargs)

        if not self.main_pdf:
            self.mkpdf(**kwargs)

        if not self.main_pdf:
            raise PDFGenerationError(
                "Pitstop validation failed because of missing pdf",
            )

        # let's work in the work dir
        pdf_file = self._move_main_pdf_to_work_dir()

        # ensure that the name of the pdf file contains a "." only
        # (for the extension), because the pitstop validation server
        # will split the filename on the first "." and get confused
        friendly_name = re.sub(r"\.pdf$", "", pdf_file)
        friendly_name = friendly_name.replace(".", "_")
        friendly_name += ".pdf"
        os.rename(pdf_file, friendly_name)
        pdf_file = friendly_name

        url = kwargs.get("pitstop_url")
        timeout = kwargs.get("timeout_pitstop", 59)
        if not url:
            raise RuntimeError("Missing pitstop_url. Please check your configuration.")

        self.task_logger.debug("PDF ready to be sent to Pitstop validation server %s.", url)

        try:
            with open(pdf_file, "rb") as pdf_filehandle:
                response = requests.post(
                    url,
                    files={
                        "userfile": (
                            pathlib.Path(pdf_file).name,  # filename
                            pdf_filehandle,
                            "application/pdf",  # mime type
                        ),
                    },
                    headers={"User-Agent": "yakunin"},
                    timeout=timeout,
                )

        except requests.exceptions.Timeout:
            self.task_logger.error("Pitstop validation timed out after %s seconds", timeout)  # noqa: TRY400
        else:
            # check the status code
            self.task_logger.debug(
                "Pitstop validation response status code is %s",
                response.status_code,
            )
            if response.status_code != 200:
                self.task_logger.error(
                    "Pitstop validation failed. Server %s returned code %s.",
                    url,
                    response.status_code,
                )
            else:
                # save the output to a new file
                zip_file = Path(
                    tempfile.mkstemp(
                        prefix=self._main_pdf_se(),
                        suffix="-pitstop.zip",
                        dir=self.work_dir,
                    )[1],
                )
                zip_file.write_bytes(response.content)
                self.task_logger.debug("Response received from Pitstop validation server.")

                # check the output
                # the server will return a text file if something went wrong
                mime = aruspica_mime(zip_file)
                if mime != "application/zip":
                    self.task_logger.error(
                        "Pitstop validation failed. Server %s returned a %s file.",
                        url,
                        mime,
                    )
                else:
                    self.task_logger.debug("PDF has been Pitstop-validated.")
                    zip_obj = zipfile.ZipFile(io.BytesIO(response.content))
                    # the typical zip file contains:
                    #  . filename-fix-task-rep.xml
                    #  . filename-fix-rep.xml
                    #  . filename-fix-rep.pdf
                    #  . filename-fix.pdf
                    #  . filename-val-task-rep.xml
                    #  . filename-val-rep.xml
                    #  . filename-val-rep.pdf
                    #  . filename-fix-val.pdf
                    #  . filename.output

                    filename_sn = re.sub(r"\.pdf$", "", pathlib.Path(pdf_file).name)

                    # The first step of the process is the "fix"
                    # let's see if the fix has been done
                    # and how it went
                    task_report_fn = f"{filename_sn}-fix-task-rep.xml"
                    report_fn = f"{filename_sn}-fix-rep.xml"
                    read_pitstop_report(zip_obj, task_report_fn, report_fn, self.task_logger, task="fix")

                    # The second step of the process is the "validation"
                    # let's see if the validation has been done
                    # and how it went
                    task_report_fn = f"{filename_sn}-val-task-rep.xml"
                    report_fn = f"{filename_sn}-val-rep.xml"
                    read_pitstop_report(
                        zip_obj,
                        task_report_fn,
                        report_fn,
                        self.task_logger,
                        task="validation",
                    )

                    # extract the fixed-and-validated pdf
                    pdf_fn = f"{filename_sn}-fix-val.pdf"
                    if pdf_fn in zip_obj.namelist():
                        zip_obj.extract(pdf_fn, path=self.temp_dir)
                        # No need to ensure unique name: clash is unlikely
                        self.main_pdf = pdf_fn
                    else:
                        self.task_logger.error("Missing %s in zip file %s", pdf_fn, zip_file)
                return self.submission_archive()

    def topdfa(self, **kwargs):
        """
        Generate PDF/A-1b via Callas' Pdftoolbox.

        Raises:
          PDFGenerationError: if we can't get a PDF to work with.
          RuntimeError: when some configuration is wrong.

        """
        app_logger.debug("PDF/A-1b requested")

        if kwargs.get("do_pitstop_validation"):
            self.pitstop_validate(**kwargs)
        else:
            # pitstop validation will take care of watermark if necessary
            # so I just test if they want a watermark when the did not ask
            # for a validation
            text = kwargs.get("text")
            if text is not None:
                self.watermark(**kwargs)

        if not self.main_pdf:
            self.mkpdf(**kwargs)

        if not self.main_pdf:
            raise PDFGenerationError("PDF/A-1b failed because of missing pdf")

        # let's work in the work dir
        pdf_file = self._move_main_pdf_to_work_dir()

        url = kwargs.get("pdfa_url")
        timeout = kwargs.get("timeout_pdfa", 59)
        if not url:
            raise RuntimeError("Missing pdfa_url. Please check your configuration.")
        self.task_logger.debug(
            "PDF ready to be sent to PDF/A transformation server %s.",
            url,
        )

        try:
            with open(pdf_file, "rb") as pdf_filehandle:
                response = requests.post(
                    url,
                    files={
                        "userfile": (
                            pathlib.Path(pdf_file).name,  # filename
                            pdf_filehandle,
                            "application/pdf",
                        ),
                    },
                    headers={"User-Agent": "yakunin"},
                    timeout=timeout,
                )
        except requests.exceptions.Timeout:
            self.task_logger.error(  # noqa: TRY400
                "PDF/A transformation timed out after %s seconds",
                timeout,
            )
        else:
            # check the status code
            self.task_logger.debug("PDF/A response status code is %s", response.status_code)
            if response.status_code != 200:
                self.task_logger.error(
                    "PDF/A transformation failed. Server %s returned code %s.",
                    url,
                    response.status_code,
                )
            else:
                # got a good response (200) from the server
                # save the output to a new file
                pdfa_name = Path(
                    tempfile.mkstemp(
                        prefix=self._main_pdf_se(),
                        dir=self.work_dir,
                    )[1],
                )
                pdfa_name.write_bytes(response.content)
                self.task_logger.debug("Response received from PDF/A transformation server.")

                # check the output
                # the server will return a text file if something went wrong
                mime = aruspica_mime(pdfa_name)
                if mime != "application/pdf":
                    self.task_logger.error(
                        "PDF/A transformation failed. Server %s returned %s file.",
                        url,
                        mime,
                    )
                else:
                    # all seems well
                    # the file received is the main pdf in PDF/A-2b format
                    self.main_pdf = pathlib.Path(pdfa_name).name
                    self.main_pdf += "-pdfa.pdf"

                    # move it from work to root dir
                    os.rename(pdfa_name, os.path.join(self.temp_dir, self.main_pdf))

                    self.task_logger.info("PDF transformed to PDF/A-1b.")
        return self.submission_archive()

    def mkpdf(self, **kwargs):
        """
        Try to generate a pdf from the given archive file.

        Raises:
          PDFGenerationError: if we can't get a PDF to work with.

        """
        app_logger.debug("mkpdf requested")
        files = list(self.work_dir.glob("**/*"))
        if not files:
            raise PDFGenerationError("No file to work with? Some error during unpack?")
        if len(files) == 1:
            mime = aruspica_mime(files[0])
            if mime == "application/pdf":
                self.main_pdf = files[0].name
                files[0].rename(self.temp_dir / self.main_pdf)

            # ODT or DOCX - transform to pdf via libreoffice
            elif mime in {
                "application/vnd.oasis.opendocument.text",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            }:
                if mime == "application/vnd.oasis.opendocument.text":
                    app_logger.debug("mkpdf received ODT file")
                else:
                    app_logger.debug("mkpdf received DOCX file")
                timeout = kwargs.get("timeout_mkpdf", 59)
                self._convert_to_pdf_via_libreoffice(file=files[0], timeout=timeout)

            # DOC - transform to pdf via Word@medusa
            elif mime == "application/msword":
                app_logger.debug("mkpdf received DOC file")
                url = kwargs.get(
                    "url_doc2pdf",
                    "https://medialab.sissa.it/ud/medusa/saveaspdf",
                )
                timeout = kwargs.get("timeout_mkpdf", 59)
                self._convert_to_pdf_via_word_on_windows(
                    files[0],
                    url=url,
                    mime=mime,
                    timeout=timeout,
                )

        if self.main_pdf is None:
            self.task_logger.debug(
                "mkpdf received a tex-related archive. Will compile",
            )
            self.tex_compile(**kwargs)

        if self.main_pdf is None:
            raise PDFGenerationError

        self.task_logger.info("Main pdf is %s", self.main_pdf)
        return self.submission_archive()

    def submission_archive(self):
        """
        Return the processed result.

        Return the path to a tar.gz containing the final pdf, the
        submission dir, the work dir, and the task log.

        """
        filename = tempfile.mkstemp()[1]
        result = shutil.make_archive(filename, "gztar", self.temp_dir)
        pathlib.Path(filename).unlink()  # TODO: not thread-safe (?)
        return result

    def read_log(self):
        """Read the compilation & co. log files and report problems."""
        # latexmk
        # =======
        # TODO: latexmk produces .fls and .fdb_latexmk files
        # I don't know how to use them...
        # 🤔 latexmk_log = os.path.join(  [off-topic] this line makes ruff ERA001 break 🙂
        #     self.work_dir, self.basename+".fls")
        # if os.path.exists(latexmk_log):
        #     task_logger.debug("%s exists", latexmk_log)  # noqa: ERA001

        # latex .log
        # ==========
        # see stdout

        # stdout
        # ======
        # This is the stdout of the latexmk command, which should
        # contain also the stdout of the latex command(s)
        # NB: not sure about the enconding (see
        # test-files/9578-dg.tar.gz)

        competent_functions = inspect.getmembers(
            log_reading_lib,
            lambda x: inspect.isfunction(x) and getattr(x, "exposed", False),
        )
        competent_functions = [x[1] for x in competent_functions]
        app_logger.debug(
            "found %s error-reading functions",
            len(competent_functions),
        )

        stdout_log = self.tex_master.with_suffix(".stdout")
        with open(stdout_log, encoding="utf-8") as stdout_file:
            self.task_logger.debug("Reading %s", stdout_log)

            # since "next()" disables "tell",
            # I'm going to iterate over the file lines in this funny faction
            # https://stackoverflow.com/a/49786016/1581629
            for line in iter(stdout_file.readline, ""):
                for func in competent_functions:
                    if line.find(func.search_string) >= 0:
                        func(line, stdout_file, self.task_logger)

    def tideup_src(self):
        """Call functions that can fix some known problem in the tex src."""
        competent_functions = inspect.getmembers(
            src_tidyup_lib,
            inspect.isfunction,
        )
        app_logger.debug("found %s src-tideup functions", len(competent_functions))
        for funcname, func in competent_functions:
            app_logger.debug("calling %s on %s", funcname, self.tex_master)
            func(self.tex_master, self.task_logger)

    def _move_main_pdf_to_work_dir(self) -> Path:
        """
        Archive the main PDF.

        Move the main pdf back to the work dir (useful when new
        processing must be applied to the main pdf (watermark,
        validation, pdfa...).

        Returns the path of the moved file.

        Raises:
          RuntimeError: when the main pdf is missing.

        """
        if not self.main_pdf:
            raise RuntimeError("Trying to move non-existing main pdf to work-dir.")
        src = self.temp_dir / self.main_pdf
        target = self.work_dir / self.main_pdf
        return src.rename(target)

    def _main_pdf_se(self):
        """Return the name of the main pdf file without the ".pdf" extension."""
        return re.sub(r"\.pdf$", "", self.main_pdf)

    def _convert_to_pdf_via_libreoffice(self, file: Path, timeout: int = 59):
        """
        Conver the file via libreoffice.

        If all goes well, self.main_pdf will be set.
        """
        # Apparently libreoffice cannot be called concurrently
        # (see e.g. https://ask.libreoffice.org/t/convert-to-commands-in-parallel-possible/90182)
        # A workaround, is to set differet UserInstallation folders for each operation,
        # so we do that:
        uniq_profile_dir = tempfile.mkdtemp()
        try:
            # Kudos to Alexandra Zaharia for the spiegone on how to kill process groups:
            # https://alexandra-zaharia.github.io/posts/kill-subprocess-and-its-children-on-timeout-python/
            process = subprocess.Popen(
                args=[
                    "libreoffice",
                    f"-env:UserInstallation=file://{uniq_profile_dir}",
                    "--headless",  # already implied by --convert-to
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    self.temp_dir,
                    str(file),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )

            stdout, stderr = process.communicate(timeout=timeout)

            if process.returncode != 0:
                self.task_logger.error("PDF generation failed:")
                self.task_logger.error(f"    error returncode: {process.returncode}")
                if stderr:
                    self.task_logger.error(f"    STDERR: {stderr.decode()}")
                if stdout:
                    self.task_logger.error(f"    STDOUT: {stdout.decode()}")

        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait()
            self.task_logger.error("PDF generation timed out after %s seconds", timeout)  # noqa: TRY400
        else:
            self.task_logger.info("PDF successfully generated.")
            if file.suffix in {".odt", ".docx"}:
                self.main_pdf = file.with_suffix(".pdf").name
            else:
                self.task_logger.error(
                    f"Unknow extension on file {self.main_pdf}. Please check!",
                )
        finally:
            shutil.rmtree(uniq_profile_dir)

    def _convert_to_pdf_via_word_on_windows(self, file, url, mime, timeout=59):
        """
        Send the file to a windows machine with Word installed and "serviceable".

        See https://auriol.medialab.sissa.it/svn/misc/doc2X-cherrypy-server/

        If all goes well, self.main_pdf will be set.

        Raises:
          PDFGenerationError: if we can't get a PDF to work with.

        """
        self.task_logger.debug(
            "DOCX %s ready to be sent to doc-to-pdf server %s.",
            file,
            url,
        )

        try:
            with open(file, "rb") as filehandle:
                response = requests.post(
                    url,
                    files={
                        "userfile": (
                            pathlib.Path(file).name,
                            filehandle,
                            mime,
                        ),
                    },
                    headers={"User-Agent": "yakunin"},
                    timeout=timeout,
                )
        except requests.exceptions.Timeout:
            self.task_logger.error(  # noqa: TRY400
                "doc-to-pdf conversion timed out after %s seconds",
                timeout,
            )
            return
        else:
            # check the status code
            if response.status_code != 200:
                self.task_logger.error(
                    "doc-to-pdf failed. Server %s returned code %s.",
                    url,
                    response.status_code,
                )
                raise PDFGenerationError

            # got a good response (200) from the server
            # save the output to a new file
            self.main_pdf = re.sub(r"\.docx?$", "", pathlib.Path(file).name)
            pdf_name = Path(
                tempfile.mkstemp(
                    prefix=self._main_pdf_se(),
                    dir=self.work_dir,
                )[1],
            )
            pdf_name.write_bytes(response.content)
            self.task_logger.debug("Response received from doc-to-pdf server.")

            # check the output
            # the server will return a text file if something went wrong
            mime = aruspica_mime(pdf_name)
            if mime != "application/pdf":
                self.task_logger.error(
                    "doc-to-pdf transformation failed. Server %s returned %s file.",
                    url,
                    mime,
                )
                raise PDFGenerationError
            # all seems well
            # the file received is the main pdf
            self.main_pdf = pathlib.Path(pdf_name).name
            self.main_pdf += ".pdf"

            # move it from work to root dir
            os.rename(pdf_name, os.path.join(self.temp_dir, self.main_pdf))

            self.task_logger.info("DOCX transformed to PDF.")
