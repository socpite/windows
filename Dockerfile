ARG VERSION_ARG="latest"
FROM scratch AS build-amd64

COPY --from=qemux/qemu:7.12 / /

ARG DEBCONF_NOWARNINGS="yes"
ARG DEBIAN_FRONTEND="noninteractive" ARG DEBCONF_NONINTERACTIVE_SEEN="true"

RUN set -eu && \
    apt-get update && \
    apt-get --no-install-recommends -y install \
	python-is-python3 \
	python3-tk \
	xvfb \
	scrot \
        wsdd2 \
        samba \
        wimtools \
        dos2unix \
        cabextract \
        libxml2-utils \
        libarchive-tools \
	pip \
        netcat-openbsd && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN mkdir -p /hud_controller/src
RUN mkdir /app
COPY --chmod=755 ./src/hud_controller /hud_controller/src/hud_controller 
COPY --chmod=755 ./pyproject.toml /hud_controller/pyproject.toml
COPY --chmod=755 ./src /run/
COPY --chmod=755 ./assets /run/assets

ADD --chmod=664 https://github.com/qemus/virtiso-whql/releases/download/v1.9.45-0/virtio-win-1.9.45.tar.xz /var/drivers.txz

FROM dockurr/windows-arm:${VERSION_ARG} AS build-arm64
FROM build-${TARGETARCH}

ARG VERSION_ARG="0.00"
RUN echo "$VERSION_ARG" > /run/version

VOLUME /storage

ENV VERSION="https://archive.org/download/tiny-11-NTDEV/tiny11%2023H2%20x64.iso"
ENV RAM_SIZE="4G"
ENV CPU_CORES="2"
ENV DISK_SIZE="64G"

COPY ./tiny11.iso /boot.iso
RUN pip install -e /hud_controller --break-system-packages

HEALTHCHECK --interval=5s --timeout=3s --retries=3 CMD \
    test -S /tmp/qmp-sock || exit 1
ENTRYPOINT ["/usr/bin/tini", "-s", "/run/entry.sh"]
