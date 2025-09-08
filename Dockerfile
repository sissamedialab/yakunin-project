# To be generated daily for security updates
ARG ML_VERSION=trixie-tl25-py313-ml2
FROM registry.gitlab.sissamedialab.it/wjs/yakunin-project/yakunin:$ML_VERSION

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked


USER root
RUN apt-get update && apt-get upgrade -y
USER app
