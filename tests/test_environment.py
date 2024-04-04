"Test that we have what's needed to compile etc."
import shutil
import subprocess
import pytest


@pytest.mark.parametrize('formato', ['gztar', 'zip', 'bztar', 'xztar'])
def test_default_formats(formato):
    "Verify that all default formats of shutil are available"
    # this actually tests the installation
    available_formats = [x[0] for x in shutil.get_archive_formats()]
    assert formato in available_formats


def test_latex_long_log_lines():
    "Verify that tex log lines are long"
    # https://tex.stackexchange.com/a/52994/56076
    result = subprocess.run(args=["kpsewhich", "texmf.cnf"],
                            check=True,
                            stdout=subprocess.PIPE)
    texmfcnf = result.stdout.decode('utf-8').strip()

    result = subprocess.run(args=["grep", "-q", "max_print_line=1000",
                                  texmfcnf],
                            check=True,
                            stdout=subprocess.PIPE)

    # if we get here it means that we have the variable max_print_line
    # set correctly
    assert True


@pytest.mark.parametrize('program',
                         ['latex',  # must be in the PATH
                          'pdftk',  # for watermarks
                          'gs',  # for watermarks
                          'libreoffice',  # for odt-to-pdf
                          ])
def test_required_programs(program):
    "Test that the required programs are installed on the system"
    assert shutil.which(program) is not None
