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

## Local development

To run Yakunin locally with all the needed dependencies (LaTeX, medialab-sty, libreoffice, pdftk, ...) but with your
local code, mount your working copy into one of the docker images (e.g. `yakunin:production`, or the
`yakunin:$ML_VERSION` image built by CI from `main`). From the root of the repository:

``` bash
docker run -ti --rm --name yakunin-dev \
  --mount type=bind,src="$PWD",dst=/workdir \
  -e PYTHONPATH=/workdir \
  -e DEBUG=True \
  -p 1235:8889 \
  registry.gitlab.sissamedialab.it/wjs/yakunin-project/yakunin:production \
  python3 yakunin_service/manage.py runserver 0.0.0.0:8889
```

The service will run at `localhost:1235` (try `curl http://localhost:1235/test/`).

What the options do:

- `--mount type=bind,src="$PWD",dst=/workdir`: replaces the code in the image with your working copy.
- `-e PYTHONPATH=/workdir`: the image also has a (non-editable) copy of `yakunin` and `yakunin_service` installed with
  pip. `manage.py` lives in `yakunin_service/`, so without this Python would import that installed copy instead of
  your local code.
- `-e DEBUG=True`: Django's debug mode (it must be the string `True`, see `yakunin_service/settings.py`).
- `-p 1235:8889`: exposes the service on `localhost:1235` (the same port as `compose.dev.yaml`).
- `-ti --rm --name yakunin-dev`: runs in the foreground (logs in the terminal, `Ctrl-C` to stop), removes the container
  when it stops and gives it a name for the `docker` commands below.
- `manage.py runserver`: the image's default command is `daphne ... yakunin_service.asgi:application`, which has no
  auto-reload; `runserver` (provided by daphne, since `daphne` is in `INSTALLED_APPS`) serves the same ASGI app and
  restarts it whenever a `.py` file changes.

The container user has uid/gid 1000:1000, so files written in your working copy (e.g. `__pycache__`) belong to you if
you have the same uid/gid (usually the case on single-user Linux machines). The yakunin log is written in
`/tmp/yakunin.log` inside the container.

To run the tests or get a shell, replace the last line with the command, e.g.:

``` bash
  ... \
  python3 -m pytest -n 8
```

### Restarting after code changes

- Changes to `.py` files are picked up automatically by `runserver` (look for `... changed, reloading.` in the logs). The
  reload restarts the whole process, so a request that is running while you save is probably cut short.
- With the image's default command (`daphne`, no auto-reload), the local code is still used (daphne puts the current
  directory `/workdir` first in Python's import path), but you need to restart the service: `docker restart
  yakunin-dev` (from another terminal), or stop it with `Ctrl-C` and run the `docker run` command again.
- If you change the dependencies in `pyproject.toml`, the image is out of date: install them in the running container
  (the changes last until the container is removed)

  ``` bash
  docker exec yakunin-dev pip install --break-system-packages \
    --extra-index-url=https://gitlab.sissamedialab.it/api/v4/projects/60/packages/pypi/simple '.[service,test]'
  ```

  or use a more recent image (or build a new one with the `build-commit-image` CI job).

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
