"Extract, compile & watermark WJ TeX archives"

import io
import glob
import os
import subprocess
import tempfile
import logging
import shutil
import re
import inspect
import zipfile
import filetype
import requests
import yakunin.log_reading_lib
import yakunin.src_tidyup_lib
from yakunin.lib import YAKUNIN_LOGGER, TASK_LOGGER, TASK_LOG
from yakunin.lib import aruspica_mime, has_documentclass, read_pitstop_report
from yakunin.exceptions import UnknownArchiveFormat
from yakunin.exceptions import NoTeXMaster
from yakunin.exceptions import PDFGenerationFailure


class Archive():
    """The internal representation of a submitted archive.
       An "archive" can be any of zip, tar.gz, xtar (see shutil.unpack_archive)
       but also a simple tex file or a pdf file
       (in this last case, some operations will fail)."""

    # non-tex files that I can receive and the I can do something with
    # e.g. if I get a pdf, I can do watermark, pdf/A, etc.
    # if I get a docx or odt, I can do to-pdf, watermark, etc.
    non_tex_known_types = (
        'application/pdf',
        'application/vnd.oasis.opendocument.text',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.temp_dir and os.path.exists(self.temp_dir):
            if YAKUNIN_LOGGER.getEffectiveLevel() == logging.DEBUG:
                YAKUNIN_LOGGER.critical("Please remove %s", self.temp_dir)
            else:
                shutil.rmtree(self.temp_dir)

    def __init__(self, tex_master=None,
                 archive=None,
                 base_dir='/tmp',
                 ):
        assert archive is not None

        self.archive_filename = archive
        self.archive_name = os.path.split(archive)[-1]
        # TODO: use only the filename/path, do not open it yet
        self.archive = io.BytesIO(open(archive, 'rb').read())
        self.archive.seek(0)

        self.tex_master = tex_master
        self.main_pdf = None

        # basename = tex_master sans extension
        self.basename = None

        self.base_dir = base_dir

        # temp dir
        # ========
        # The folders "submission" and "work", the task log and the
        # main pdf will be created inside this dir
        self.temp_dir = tempfile.mkdtemp(dir=self.base_dir)

        # application logger
        # ==================
        # Everything starts here, so I should be able to initialize the
        # application logger here.

        # This logger writes to a "yakunin.log" file in the temp_dir
        # all relevant steps of the required task. The "yakunin.log"
        # is a mean to communicate with the calling wjapp application.
        # Now I know where temp_dir is, so here I change the logger's
        # handler filename
        log_stream = open(os.path.join(self.temp_dir, TASK_LOG),
                          'wt')
        # no handler defined during tests?
        for handler in TASK_LOGGER.handlers:
            handler.setStream(log_stream)
        TASK_LOGGER.debug("Working in %s", self.temp_dir)

        self.work_dir = None

        self.mime_type = None
        # shutil format for unpack_archive function
        self.formato = None

    def _unpack_archive(self):
        """Save the archive in a temporary location
           uncompress the archive (if needed)
           Edge case: if the received "archive" is a pdf,
           just save the file in a temporary location
           NB: some operations might fail"""

        assert os.path.isdir(self.temp_dir)

        # submission dir
        # ==============
        # contains the received file
        submission_dir = os.path.join(self.temp_dir, 'submission')
        os.mkdir(submission_dir)
        archive_file = os.path.join(submission_dir, self.archive_name)
        with open(os.path.join(archive_file), 'wb') as received_file:
            received_file.write(self.archive.read())
        self.archive.seek(0)

        # work dir
        # ========
        # where compilation/watermarking/etc. takes place
        self.work_dir = os.path.join(self.temp_dir, 'work')
        assert not os.path.exists(self.work_dir)
        os.mkdir(self.work_dir)

        # mime type
        # =========
        self.mime_type = aruspica_mime(self.archive_filename)
        # TODO: should be aruspica_mime(self.submission + self.archive_name)
        # is this too much of an assumption?
        assert self.mime_type is not None
        TASK_LOGGER.debug("Archive mime type: %s", self.mime_type)

        # now that we have a mimetype, lets find a suitable format for
        # shutil.unpack_archive
        epatografo = {
            'text/x-tex': 'copy',
            'application/pdf': 'copy',
            'application/zip': 'zip',
            'application/x-tar': 'tar',
            'application/x-compressed-tar': 'gztar',
            'application/x-bzip-compressed-tar': 'bztar',
            'application/gzip': 'gz',
            'application/x-bzip2': 'bz',
            'application/x-rar': 'any',
            'application/vnd.oasis.opendocument.text': 'copy',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'copy',
        }
        if self.mime_type not in epatografo:
            TASK_LOGGER.error("Unknown archive format %s",
                              self.mime_type)
            raise UnknownArchiveFormat()

        self.formato = epatografo[self.mime_type]

        # extract/write files
        # ===================
        # TODO: switch to patool? https://libraries.io/pypi/patool
        try:
            shutil.unpack_archive(archive_file, self.work_dir, self.formato)
        except (shutil.ReadError) as exception:
            YAKUNIN_LOGGER.warning("Cannot upack %s as %s: %s",
                                   archive_file, self.formato, exception)
            raise exception
        else:
            TASK_LOGGER.info("Unpacked %s as %s",
                             archive_file, self.formato)

        os.chdir(self.work_dir)

    def find_master(self):
        """navigate the archive and find the tex_master"""
        if not self.work_dir:
            # archive has not yet been unpacked;
            # do the upacking
            self._unpack_archive()

        if self.tex_master:
            TASK_LOGGER.info("TeX master (given): %s", self.tex_master)
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
        files = glob.glob('**/*', recursive=True)
        assert files, "No file to work with? Some error during unpack?"
        if len(files) == 1:
            mime = filetype.guess_mime(files[0])
            YAKUNIN_LOGGER.debug("Mime of master %s is %s", files[0], mime)
            if mime in Archive.non_tex_known_types:
                TASK_LOGGER.warning("Mime of master %s is %s. Not TeX!",
                                    files[0], mime)
                # do not set tex_master and raise an exception
                raise NoTeXMaster()
            # else, we the mime type is good
            self.tex_master = files[0]
            return

        # More files
        # ==========

        # .tex
        tex_files = list(
            filter(lambda x: x.endswith(".tex") or x.endswith(".TEX"),
                   files))

        if len(tex_files) == 1:
            self.tex_master = list(tex_files)[0]
            TASK_LOGGER.debug("Many files, but only one .tex. Master is %s",
                              self.tex_master)
            return

        # many .tex
        if tex_files:
            # tieni solo quelli che contengono \documentclass
            tex_files = list(filter(has_documentclass, tex_files))
            # TODO: what if no tex has \documentclass???
            # se c'è un main.tex usa quello
            if 'main.tex' in tex_files:
                self.tex_master = 'main.tex'
            else:
                # altrimenti prendi quello più vicino alla radice
                tex_files = sorted(tex_files,
                                   key=lambda x: len(os.path.split(x)))
                self.tex_master = tex_files[0]
            TASK_LOGGER.info("TeX master (found %s with \\documentclass): %s",
                             len(tex_files),
                             self.tex_master)
            return

        # no .tex
        YAKUNIN_LOGGER.error("WRITE ME!!!")

    def compile(self, **kwargs):
        """compile a tex (run tex_engine on the tex_master)"""
        # TODO: read the following:
        # A Decorator-Based Build System
        # https://www.artima.com/weblogs/viewpost.jsp?thread=241209
        if not self.tex_master:
            self.find_master()
        if not self.work_dir:
            self._unpack_archive()
        # if not tex_engine:
        #     tex_engine = 'pdflatex'

        tex_engine = kwargs.get('tex_engine', 'latexmk -pdf')
        tex_options = ['-interaction=nonstopmode', ]

        timeout = kwargs.get('timeout_compilation', 13)

        assert self.tex_master
        assert tex_engine

        # the tex master can be inside a subdir of "work"
        # we move there and keep only the basename of the tex master
        self.work_dir = os.path.join(self.work_dir,
                                     os.path.dirname(self.tex_master))
        os.chdir(self.work_dir)
        self.tex_master = os.path.basename(self.tex_master)

        self.basename = re.sub(r"\.tex$", "",
                               self.tex_master, flags=re.IGNORECASE)

        # correct known problems in the tex source
        self.tideup_src()

        # build the compilation command
        args = tex_engine.split()
        args.extend(tex_options)
        args.append(self.tex_master)

        TASK_LOGGER.debug("ready to compile %s in %s with command %s",
                          self.tex_master,
                          os.getcwd(),
                          ' '.join(args))
        stdout = None
        try:
            # NB: do not use "encoding='utf-8'"
            # because pesky files have broken encodings
            result = subprocess.run(
                args=args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=timeout)
        except subprocess.CalledProcessError as error:
            # Here I log a warning.
            # Later on, I will examine the situation more accurately
            # an decide whether to eventually log a blockin error
            TASK_LOGGER.warning(error)
            # stdout/stderr can be taken from the exception
            stdout = error.stdout
        except subprocess.TimeoutExpired as error:
            TASK_LOGGER.error("Compilation timed out after %s seconds",
                              timeout)
            stdout = error.stdout
        else:
            TASK_LOGGER.info("Successfully compiled %s",
                             self.tex_master)
            stdout = result.stdout
        finally:
            # dump all stdout/stderr to basename.stdout
            if stdout is not None:
                with open(os.path.join(self.work_dir,
                                       self.basename+".stdout"), 'wb') as out:
                    out.write(stdout)

        # read the logs (latexmk, latex, etc.)
        # and log away problems as needed
        self.read_log()

        # move the final pdf to the "root" of the temp_dir
        self.main_pdf = self.basename + ".pdf"
        generated_pdf = os.path.join(self.work_dir, self.main_pdf)
        if os.path.exists(generated_pdf):
            os.rename(generated_pdf,
                      os.path.join(self.temp_dir, self.main_pdf))
        else:
            TASK_LOGGER.error("No pdf file produced! Compilation fails.")

        return self.submission_archive()

    def watermark(self, **kwargs):
        """The given watermark is applied to the given height on the
        right-hand side of the page. If the page is in landscape, the
        watermark is still applied to the long edge. It is assumed
        that the page is rotated clock-wise, so the watermark will be
        on the bottom.

        """
        # using same approach as https://auriol/svn/misc/watermark
        # for an alternative, see https://stackoverflow.com/a/49471012/1581629

        text = kwargs.get('text', 'DRAFT')
        wm_x = kwargs.get('x', '550')
        wm_y = kwargs.get('y', '620')
        # TODO: timeout is difficult for watermark because we have many steps

        YAKUNIN_LOGGER.debug('watermark requested: "%s"@(%s, %s)',
                             text, wm_x, wm_y)

        if not self.main_pdf:
            self.mkpdf(**kwargs)

        if not self.main_pdf:
            raise PDFGenerationFailure(
                "Watermarking failed because of missing pdf")

        # parenthesis must be escaped when used in postscript
        text = re.sub(r'([()])', r'\\\1', text)

        # let's work in the work dir
        pdf_file = self._move_main_pdf_to_work_dir()

        # TODO: manage explicit page selection:
        # e.g.: watermark.sh -r3east 15west 16north JCAP_040P_1216.pdf ...

        # run pdfinfo to find pg. number and rotated pages
        # (need -f / -l for rotation info, assuming pdf < 1000 pages)
        # https://stackoverflow.com/a/29647772/1581629

        # TODO use try/except
        result = subprocess.run(args=['pdfinfo',
                                      '-f',
                                      '1',
                                      '-l',
                                      '1000',
                                      # '-box',  # \Mediabox & co.
                                      pdf_file],
                                stdout=subprocess.PIPE,
                                universal_newlines=True,
                                check=True)
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
        degrees_to_orientation = {
            '0': '0',
            '90': '3',
            '180': '2',
            '270': '1'
        }
        num_pages = None
        for line in io.StringIO(result.stdout):
            # read the number of pages (how long the pdf file is)
            if num_pages is None:
                match = re.match(pages_pattern, line)
                if match:
                    num_pages = int(match.group('pg_num'))
                    continue

            # check if any page is rotated
            match = re.match(rotation_pattern, line)
            if match:
                rotation = match.group('rotation')
                if rotation == '0':
                    continue
                page = match.group('pg_num')

                # prepare "orientations" for pdftk
                # if the rotation is not 90 or 270
                # report a warning but do not rotate
                # (since I've never seen anything else)
                orientation = degrees_to_orientation.get(rotation, '0')
                if orientation == '0':
                    TASK_LOGGER.warning(
                        "Found page %s rotated by %d degrees. "
                        "Applying watermark as if there was no rotation. "
                        "Please check.", page, rotation)
                    continue
                pages_to_rotate[page] = orientation

        # auxiliary files
        # the watermark in a postscript file
        dummy, watermark_ps_name = tempfile.mkstemp(
            prefix="watermark", suffix=".ps",
            dir=os.getcwd())

        # the pdf watermark (generated from the ps)
        dummy, watermark_name = tempfile.mkstemp(
            prefix="watermark", suffix=".pdf",
            dir=os.getcwd())

        # the final result (the main pdf watermarked)
        dummy, watermarked_name = tempfile.mkstemp(
            prefix=self._main_pdf_se(),
            suffix="-wm.pdf",
            dir=os.getcwd())
        del dummy  # only to avoid "unused-variable warning"

        if not pages_to_rotate:
            # Prepare and apply a single watermark

            # Prepare the watermark:
            # first make a postscript file
            # (A4 portrait page with wm on the right-hand side)
            # generate the pdf from the ps
            # and finally apply it to the main pdf

            # create the postscript file
            with open(watermark_ps_name, 'w') as dst:
                dst.write(
                    f"{wm_x} {wm_y} moveto -90 rotate 0.75 setgray "
                    "/Courier findfont 30 scalefont setfont "
                    f"({text}) show")

            # generate the pdf from the ps
            subprocess.run(
                args=["gs",
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
                      watermark_ps_name],
                check=True)

            # apply the watermark
            subprocess.run(
                args=["pdftk",
                      self.main_pdf,
                      "background",
                      watermark_name,
                      "output",
                      watermarked_name],
                check=True)

        else:
            TASK_LOGGER.debug(
                "Rotating watermark for pages %s",
                pages_to_rotate)

            # create the postscript code
            # https://stackoverflow.com/a/15756108/1581629
            postscript_code = f"""%!PS- Adobe-3.0
%%Pages: {num_pages}
%%EndComments
"""
            for i in range(1, num_pages+1):
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
            with open(watermark_ps_name, 'w') as dst:
                dst.write(postscript_code)

            # generate the pdf from the ps
            subprocess.run(
                args=["gs",
                      "-P-",
                      "-q",
                      "-dSAFER",
                      "-dNOPAUSE",
                      "-dBATCH",
                      f"-sOutputFile={watermark_name}",
                      "-sDEVICE=pdfwrite",
                      "-sPAPERSIZE=a4",
                      "-dAutoRotatePages=/None",
                      watermark_ps_name],
                check=True)

            # apply the multibackground
            subprocess.run(
                args=["pdftk",
                      self.main_pdf,
                      "multibackground",
                      watermark_name,
                      "output",
                      watermarked_name],
                check=True)

        self.main_pdf = os.path.basename(watermarked_name)
        os.rename(watermarked_name,
                  os.path.join(self.temp_dir, self.main_pdf))
        TASK_LOGGER.debug("Watermark applied.")
        return self.submission_archive()

    def pitstop_validate(self, **kwargs):
        "Execute Pitstop fix & validation of the given PDF file."
        YAKUNIN_LOGGER.debug("Pitstop validation requested")

        text = kwargs.get('text', None)
        if text is not None:
            self.watermark(**kwargs)

        if not self.main_pdf:
            self.mkpdf(**kwargs)

        if not self.main_pdf:
            raise PDFGenerationFailure(
                "Pitstop validation failed because of missing pdf")

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

        url = kwargs.get('pitstop_url', None)
        timeout = kwargs.get('timeout_pitstop', 59)
        assert url is not None
        TASK_LOGGER.debug(
            "PDF ready to be sent to Pitstop validation server %s.",
            url)

        try:
            response = requests.post(
                url,
                files={
                    'userfile': (os.path.basename(pdf_file),  # filename
                                 open(pdf_file, 'rb'),  # filehandle
                                 'application/pdf')  # mime type
                },
                headers={'User-Agent': 'yakunin'},
                timeout=timeout
            )
        except requests.exceptions.Timeout:
            TASK_LOGGER.error(
                "Pitstop validation timed out after %s seconds",
                timeout)
        else:
            # check the status code
            TASK_LOGGER.debug("Pitstop validation response status code is %s",
                              response.status_code)
            if response.status_code != 200:
                TASK_LOGGER.error(
                    "Pitstop validation failed. Server %s returned code %s.",
                    url,
                    response.status_code)
            else:
                # save the output to a new file
                dummy, zip_file = tempfile.mkstemp(
                    prefix=self._main_pdf_se(),
                    suffix="-pitstop.zip",
                    dir=self.work_dir)
                del dummy

                with open(zip_file, "wb") as output:
                    output.write(response.content)
                TASK_LOGGER.debug(
                    "Response received from Pitstop validation server.")

                # check the output
                # the server will return a text file if something went wrong
                mime = aruspica_mime(zip_file)
                if mime != 'application/zip':
                    TASK_LOGGER.error(
                        "Pitstop validation failed. Server %s returned a %s file.",
                        url, mime)
                else:
                    TASK_LOGGER.debug("PDF has been Pitstop-validated.")
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

                    filename_sn = re.sub(r"\.pdf$", "",
                                         os.path.basename(pdf_file))

                    # The first step of the process is the "fix"
                    # let's see if the fix has been done
                    # and how it went
                    task_report_fn = f"{filename_sn}-fix-task-rep.xml"
                    report_fn = f"{filename_sn}-fix-rep.xml"
                    read_pitstop_report(zip_obj, task_report_fn, report_fn,
                                        task='fix')

                    # The second step of the process is the "validation"
                    # let's see if the validation has been done
                    # and how it went
                    task_report_fn = f"{filename_sn}-val-task-rep.xml"
                    report_fn = f"{filename_sn}-val-rep.xml"
                    read_pitstop_report(zip_obj, task_report_fn, report_fn,
                                        task='validation')

                    # extract the fixed-and-validated pdf
                    pdf_fn = f'{filename_sn}-fix-val.pdf'
                    if pdf_fn in zip_obj.namelist():
                        zip_obj.extract(pdf_fn, path=self.temp_dir)
                        # No need to ensure unique name: clash is unlikely
                        self.main_pdf = pdf_fn
                    else:
                        TASK_LOGGER.error("Missing %s in zip file %s",
                                          pdf_fn, zip_file)
                return self.submission_archive()

    def topdfa(self, **kwargs):
        "Generate PDF/A-1b via Callas' Pdftoolbox"
        YAKUNIN_LOGGER.debug("PDF/A-1b requested")

        if kwargs.get('do_pitstop_validation', False):
            self.pitstop_validate(**kwargs)
        else:
            # pitstop validation will take care of watermark if necessary
            # so I just test if they want a watermark when the did not ask
            # for a validation
            text = kwargs.get('text', None)
            if text is not None:
                self.watermark(**kwargs)

        if not self.main_pdf:
            self.mkpdf(**kwargs)

        if not self.main_pdf:
            raise PDFGenerationFailure(
                "PDF/A-1b failed because of missing pdf")

        # let's work in the work dir
        pdf_file = self._move_main_pdf_to_work_dir()

        url = kwargs.get('pdfa_url', None)
        timeout = kwargs.get('timeout_pdfa', 59)
        assert url is not None
        TASK_LOGGER.debug(
            "PDF ready to be sent to PDF/A transformation server %s.",
            url)

        try:
            response = requests.post(
                url,
                files={
                    'userfile': (os.path.basename(pdf_file),  # filename
                                 open(pdf_file, 'rb'),  # filehandle
                                 'application/pdf')  # mime type
                },
                headers={'User-Agent': 'yakunin'},
                timeout=timeout
            )
        except requests.exceptions.Timeout:
            TASK_LOGGER.error(
                "PDF/A transformation timed out after %s seconds",
                timeout)
        else:
            # check the status code
            TASK_LOGGER.debug("PDF/A response status code is %s",
                              response.status_code)
            if response.status_code != 200:
                TASK_LOGGER.error(
                    "PDF/A transformation failed. Server %s returned code %s.",
                    url,
                    response.status_code)
            else:
                # got a good response (200) from the server
                # save the output to a new file
                dummy, pdfa_name = tempfile.mkstemp(
                    prefix=self._main_pdf_se(),
                    dir=self.work_dir)
                del dummy

                with open(pdfa_name, "wb") as output:
                    output.write(response.content)
                TASK_LOGGER.debug(
                    "Response received from PDF/A transformation server.")

                # check the output
                # the server will return a text file if something went wrong
                mime = aruspica_mime(pdfa_name)
                if mime != 'application/pdf':
                    TASK_LOGGER.error(
                        "PDF/A transformation failed. Server %s returned %s file.",
                        url,
                        mime)
                else:
                    # all seems well
                    # the file received is the main pdf in PDF/A-2b format
                    self.main_pdf = os.path.basename(pdfa_name)
                    self.main_pdf += "-pdfa.pdf"

                    # move it from work to root dir
                    os.rename(pdfa_name,
                              os.path.join(self.temp_dir, self.main_pdf))

                    TASK_LOGGER.info("PDF transformed to PDF/A-1b.")
        return self.submission_archive()

    def mkpdf(self, **kwargs):
        "Try to generate a pdf from the given archive file"
        YAKUNIN_LOGGER.debug("mkpdf requested")

        if not self.work_dir:
            self._unpack_archive()

        files = glob.glob('**/*', recursive=True)
        assert files, "No file to work with? Some error during unpack?"
        if len(files) == 1:
            mime = aruspica_mime(files[0])
            if mime == 'application/pdf':
                self.main_pdf = files[0]
                os.rename(self.main_pdf,
                          os.path.join(self.temp_dir, self.main_pdf))

            # ODT - transform to pdf via libreoffice
            elif mime == "application/vnd.oasis.opendocument.text":
                YAKUNIN_LOGGER.debug("mkpdf received ODT file")
                timeout = kwargs.get('timeout_mkpdf', 59)
                try:
                    # convert odt to pdf
                    # and save the result in root dir (temp_dir)
                    subprocess.run(
                        args=['libreoffice',
                              '--headless',  # already implied by --convert-to
                              '--convert-to',
                              'pdf',
                              '--outdir',
                              self.temp_dir,
                              files[0]],
                        check=True,
                        timeout=timeout,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT)
                except subprocess.CalledProcessError as error:
                    TASK_LOGGER.error("PDF generation from ODT failed: %s",
                                      error)
                except subprocess.TimeoutExpired:
                    TASK_LOGGER.error("Compilation timed out after %s seconds",
                                      timeout)
                else:
                    TASK_LOGGER.info("PDF successfully generated.")
                    self.main_pdf = re.sub(r'\.odt$', ".pdf", files[0])

            # DOCX - transform to pdf via Word@medusa
            elif mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                YAKUNIN_LOGGER.debug("mkpdf received DOCX file")
                url = kwargs.get(
                    'url_doc2pdf',
                    'https://medialab.sissa.it/ud/medusa/saveaspdf')
                timeout = kwargs.get('timeout_mkpdf', 59)

                TASK_LOGGER.debug(
                    "DOCX %s ready to be sent to doc-to-pdf server %s.",
                    files[0],
                    url)

                try:
                    response = requests.post(
                        url,
                        files={
                            'userfile': (os.path.basename(files[0]),
                                         open(files[0], 'rb'),
                                         mime)
                        },
                        headers={'User-Agent': 'yakunin'},
                        timeout=timeout
                    )
                except requests.exceptions.Timeout:
                    TASK_LOGGER.error(
                        "doc-to-pdf conversion timed out after %s seconds",
                        timeout)
                    return
                else:
                    # check the status code
                    if response.status_code != 200:
                        TASK_LOGGER.error(
                            "doc-to-pdf failed. Server %s returned code %s.",
                            url,
                            response.status_code)
                        raise PDFGenerationFailure()

                    else:
                        # got a good response (200) from the server
                        # save the output to a new file
                        self.main_pdf = re.sub(r"\.docx?$",
                                               "",
                                               os.path.basename(files[0]))
                        pdf_name = tempfile.mkstemp(
                            prefix=self._main_pdf_se(),
                            dir=self.work_dir)[1]

                        with open(pdf_name, "wb") as output:
                            output.write(response.content)
                            TASK_LOGGER.debug(
                                "Response received from doc-to-pdf server.")

                        # check the output
                        # the server will return a text file if something went wrong
                        mime = aruspica_mime(pdf_name)
                        if mime != 'application/pdf':
                            TASK_LOGGER.error(
                                "doc-to-pdf transformation failed. "
                                "Server %s returned %s file.",
                                url,
                                mime)
                            raise PDFGenerationFailure()
                        else:
                            # all seems well
                            # the file received is the main pdf
                            self.main_pdf = os.path.basename(pdf_name)
                            self.main_pdf += ".pdf"

                            # move it from work to root dir
                            os.rename(pdf_name,
                                      os.path.join(self.temp_dir,
                                                   self.main_pdf))

                            TASK_LOGGER.info("DOCX transformed to PDF.")

        if self.main_pdf is None:
            TASK_LOGGER.debug(
                "mkpdf probably received a tex archive. Will compile",)
            self.compile(**kwargs)

        if self.main_pdf is None:
            raise PDFGenerationFailure()

        TASK_LOGGER.info("Main pdf is %s", self.main_pdf)
        return self.submission_archive()

    def submission_archive(self):
        """Return the path to a tar.gz containing the final pdf,
           the submission dir, the work dir, and the task log"""
        if not self.work_dir:
            self._unpack_archive()
        filename = tempfile.mkstemp()[1]
        result = shutil.make_archive(filename,
                                     'gztar',
                                     self.temp_dir)
        os.unlink(filename)  # TODO: not thread-safe (?)
        return result

    def read_log(self):
        "Read the compilation & co. log files and report problems"

        # latexmk
        # =======
        # latexmk produces .fls and .fdb_latexmk files
        # I don't know how to use them...
        # latexmk_log = os.path.join(
        #     self.work_dir, self.basename+".fls")
        # if os.path.exists(latexmk_log):
        #     TASK_LOGGER.debug("%s exists", latexmk_log)

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
            yakunin.log_reading_lib,
            lambda x: inspect.isfunction(x) and getattr(x, 'exposed', False))
        competent_functions = [x[1] for x in competent_functions]
        YAKUNIN_LOGGER.debug("found %s error-reading functions",
                             len(competent_functions))

        stdout_log = os.path.join(
            self.work_dir, self.basename+".stdout")
        with open(stdout_log) as stdout_file:
            TASK_LOGGER.debug("Reading %s", stdout_log)

            # since "next()" disables "tell",
            # I'm going to iterate over the file lines in this funny faction
            # https://stackoverflow.com/a/49786016/1581629
            for line in iter(stdout_file.readline, ''):
                for func in competent_functions:
                    if line.find(func.search_string) >= 0:
                        func(line, stdout_file)

    def tideup_src(self):
        "Call functions that can fix some known problem in the tex src"
        competent_functions = inspect.getmembers(
            yakunin.src_tidyup_lib,
            inspect.isfunction)
        # competent_functions = [x[1] for x in competent_functions]
        YAKUNIN_LOGGER.debug("found %s src-tideup functions",
                             len(competent_functions))
        for (funcname, func) in competent_functions:
            YAKUNIN_LOGGER.debug('calling %s on %s',
                                 funcname, self.tex_master)
            func(self.tex_master)

    def _move_main_pdf_to_work_dir(self):
        """Move the main pdf back to the work dir (useful when new processing
must be applied to the main pdf (watermark, validation, pdfa...)"""
        assert self.main_pdf is not None
        pdf_file = os.path.join(self.work_dir, self.main_pdf)
        os.rename(
            os.path.join(self.temp_dir, self.main_pdf), pdf_file)
        os.chdir(self.work_dir)  # ← is this a good idea???
        # TODO: self.main_pdf now is WRONG! should I set it to None?
        return pdf_file

    def _main_pdf_se(self):
        'Return the name of the main pdf file without the ".pdf" extension'
        return re.sub(r"\.pdf$", "", self.main_pdf)
