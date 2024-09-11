# To be generated daily for security updates
FROM registry.gitlab.sissamedialab.it/wjs/yakunin-project/yakunin-base:latest

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/root/.cache/pip

RUN apt-get update && apt-get upgrade -y

COPY . /workdir
WORKDIR /workdir
RUN pip install --extra-index-url=https://gitlab.sissamedialab.it/api/v4/projects/60/packages/pypi/simple --break-system-packages .[service,test]

CMD ["yakunin-start"]
