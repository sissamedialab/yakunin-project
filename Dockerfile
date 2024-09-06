FROM registry.gitlab.sissamedialab.it/wjs/jcomassistant-project/ja-base:latest

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/root/.cache/pip

RUN apt-get update && apt-get install -y unoconv libreoffice

# Run libreoffice initialization and quit
RUN libreoffice --headless --terminate_after_init

# keep on separate layer because I'm not sure if always intalling pytest is a good idea:
RUN apt-get install -y python3-pytest python3-pytest-xdist
