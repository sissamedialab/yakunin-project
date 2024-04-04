tests setup
===========

# install yakunin
python3 -m venv v
. ./v/bin/activate
pip install -U pip
pip install <PATH-TO>/yakunin.tar.gz

# checkou the tests
# and install tests' requirements
svn co https://auriol/svn/misc/yakunin-project/with-script/tests
pip install -r tests/requirements.txt

# run the tests
# (user must have ssh-key on jhep@bertieri)
pytest tests


test-files
==========

The file test-files/expected_results.xml specifies the command
(function) to execute and the log-lines and (maybe) the files that one
should find in the results.


remote web servers
==================

Yakunin interacts with remote server for doc2pdf, pitstop validation,
pdfa. In order to debug the requests sent by the script, one can use
the dump_server (make a virtualenv, install tornado, and run __init__,
then redirect you requests to localhost:8888).


some notes on particular test-files
===================================

9578-dg.tar.gz
  ! Package inputenc Error: Invalid UTF-8 byte "A8.
  texlive 2016, 2017 → OK
  texlive 2018, 2019 → FAIL
  re-code from latin1 to utf8


30498-SEVRISMONRITresub2.zip
  falso allarme (l'utente aveva sottomesso un docx con le risposte al referee)


30480-Agudov_JSTAT_15.09.19.zip
  Package inputenc Error: Invalid UTF-8 byte "A0.
  Package inputenc Error: Invalid UTF-8 byte sequence.
  come 9578


141908-56076.tex
  impossible document (never settling) from
  https://tex.stackexchange.com/a/141908/56076
  30437-Generative_adversarial_networks.zip
  MUST FAIL...


30437-Generative_adversarial_networks.zip
  2 tex files


30471-JCAP_R1.zip
  Undefined control sequence
  MUST FAIL...
