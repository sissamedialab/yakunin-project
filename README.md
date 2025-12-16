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
pip install yakunin[test,service]
yakunin -h
yakunin --verify-env
```

## Run it as a service

```sh
DJANGO_SETTINGS_MODULE=yakunin_service.settings daphne -p 8889 yakunin_service.asgi:application
```

## Docker

To run the docker image locally

```sh
# login (if not already logged-in[*])
docker login gitlab.sissamedialab.it

# get the image
docker pull registry.gitlab.sissamedialab.it/wjs/yakunin-project/yakunin:latest

# run a container form the image
docker run --name yakunin --rm -p 1235:8889 registry.gitlab.sissamedialab.it/wjs/yakunin-project/yakunin:latest

```

[*] See [here](https://docs.gitlab.com/ee/user/packages/container_registry/authenticate_with_container_registry.html)
for details.

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

## Docker

Start a container (see above) and send your file to the appropriate handler:

```sh
curl -F file=@x.docx http://localhost:1235/mkpdf -o x.tar.gz
```

### How to use

- for local usage / development use `compose.dev.yaml` file for docker compose commands
- create `.env` file with the following content: `HOST_IP=172.17.0.1` (or whatever your docker host IP is, verify with
  `docker inspect bridge` and use the value from IPAM -> Config -> Gateway)
- `docker compose -f compose.dev.yaml build`
- `docker compose -f compose.dev.yaml up`
- (from another terminal) `curl http://localhost:1235/test/`
- start listening on the websocket that will be used for feedback
    - (e.g. using `websocat` from the CLI) `websocat wss://jcom.localdomain.net/ws/feedback/abc-123/`
    - see also firefox extension [WebSocket Weasel](https://github.com/mhgolkar/Weasel)
- run
  ```shell
  curl -F file=@/tmp/aaa.docx -F feedback_ws_url=wss://jcom.localdomain.net/ws/feedback/abc-123/ http://localhost:1235/mkpdf/ws/ -o /dev/null
  ```
  where:
    - `abc-123` is the name of a websocket that will report feedback while the `mkpdf` conversion is running
    - and `feedback_ws_url` must point to a WJS site (e.g. `ws://jcom:8000/ws/feedback/abc-123/`)
- to run in conjunction with wjs-submission you must run `qcluster` command and set `sync=False` in `Q_CLUSTER` in
  `settings.py`
