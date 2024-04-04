# -*- encoding: utf-8 -*-

"Test the application of a watermark"
import os
import io
from subprocess import check_output
import numpy as np
from PIL import Image
import pytest
from yakunin.archive import Archive
from conftest import ARCHIVES_DIR, well_formed


def pdfs_equals_p(file_a, file_b):
    """Compare 2 pdf files pixel-wise
    The two files must have the same number of pages;
    each page is transformed into a raster image
    and the couples are compared"""

    num_pages = get_num_pages(file_a)
    assert num_pages == get_num_pages(file_b)

    for page in range(1, num_pages+1):

        # from PIL.Image to np array
        # https://stackoverflow.com/a/14140796/1581629
        array_a = np.array(
            pdftopng(file_a, page))

        array_b = np.array(
            pdftopng(file_b, page))

        # np subtraction does not do saturation
        # (i.e. it can overflow)
        # https://stackoverflow.com/a/45817868/1581629
        # array_c = np.subtract(array_a, array_b)

        # https://stackoverflow.com/a/8538444/1581629
        # Image.fromarray(array_c).save("/tmp/aaaa.png")

        should_be_zero = np.subtract(array_a, array_b).sum()

        if should_be_zero != 0:
            return False

    return True


# pdf-diff3 https://github.com/JoshData/pdf-diff
def pdftopng(pdffile, pagenumber, width=900):
    "Rasterizes a page of a PDF."
    pngbytes = check_output(
        args=["pdftoppm",
              "-f", str(pagenumber),
              "-l", str(pagenumber),
              "-scale-to", str(width),
              "-png",
              pdffile])
    img = Image.open(io.BytesIO(pngbytes))
    return img.convert("RGB")


# https://stackoverflow.com/a/47169350/1581629
def get_num_pages(pdf_path):
    "Return the number of pages of the given pdf file"
    output = check_output(["pdfinfo", pdf_path]).decode()
    pages_line = [line for line in output.splitlines() if "Pages:" in line][0]
    num_pages = int(pages_line.split(":")[1])
    return num_pages


def test_simple_pdf():
    "Apply a watermak on a simple pdf"
    pdf_file = "14-test.pdf"
    pdf_file_path = os.path.join(ARCHIVES_DIR, pdf_file)
    target_pdf_file = "14-test-wm.pdf"
    target_pdf_file_path = os.path.join(ARCHIVES_DIR, target_pdf_file)
    archive = Archive(archive=pdf_file_path)
    archive.watermark(text="ciao")

    # open the result, and check the pdf
    result = archive.submission_archive()
    with well_formed(result) as (tmp_dir, files):
        assert archive.main_pdf in files

        os.chdir(tmp_dir)
        assert pdfs_equals_p(archive.main_pdf, target_pdf_file_path)


# def test_non_ascii():
#     "What happens if the watermark contains non-ascii chars?"
#     assert False
# who cares...

KNOWN_POSITIONS = (
    ('14-test-wm-0-100.pdf', 0, 100),
    ('14-test-wm-300-400.pdf', 300, 400),
    ('14-test-wm-580-830.pdf', 580, 830),
)
@pytest.mark.parametrize('target_pdf_file,x,y', KNOWN_POSITIONS)
def test_position(target_pdf_file, x, y):
    "Give different heights to the wm function"
    pdf_file = "14-test.pdf"
    pdf_file_path = os.path.join(ARCHIVES_DIR, pdf_file)

    target_pdf_file_path = os.path.join(ARCHIVES_DIR, target_pdf_file)
    archive = Archive(archive=pdf_file_path)
    archive.watermark(text="ciao", x=x, y=y)

    # open the result, and check the pdf
    result = archive.submission_archive()
    with well_formed(result) as (tmp_dir, files):
        assert archive.main_pdf in files

        os.chdir(tmp_dir)
        # import pdb
        # pdb.set_trace()
        assert pdfs_equals_p(archive.main_pdf, target_pdf_file_path)


def test_rotated_pages():
    """Watermark pdf file with rotated pages;
    the pdf has been generated from the compilation of an archive"""

    pdf_file = "23-wm-rotated.tar.gz"
    pdf_file_path = os.path.join(ARCHIVES_DIR, pdf_file)
    target_pdf_file = "23-wm-rotated-wm.pdf"
    target_pdf_file_path = os.path.join(ARCHIVES_DIR, target_pdf_file)
    archive = Archive(archive=pdf_file_path)
    archive.watermark(text="ciao")

    # open the result, and check the pdf
    result = archive.submission_archive()
    with well_formed(result) as (tmp_dir, files):
        assert archive.main_pdf in files

        os.chdir(tmp_dir)
        assert pdfs_equals_p(archive.main_pdf, target_pdf_file_path)
