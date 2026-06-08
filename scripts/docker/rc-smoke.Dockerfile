FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ARG GIT_LFS_VERSION=3.7.1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        openssh-client \
        python3 \
        python3-venv \
        rsync \
        xvfb \
        xauth \
        libasound2 \
        libatomic1 \
        libdbus-1-3 \
        libegl1 \
        libfontconfig1 \
        libfreetype6 \
        libgl1 \
        libglu1-mesa \
        libglib2.0-0 \
        libice6 \
        libnss3 \
        libopengl0 \
        libpcre2-16-0 \
        libpulse-mainloop-glib0 \
        libsm6 \
        libx11-6 \
        libx11-xcb1 \
        libxau6 \
        libxcb1 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-shm0 \
        libxcb-sync1 \
        libxcb-util1 \
        libxcb-xfixes0 \
        libxcb-xinerama0 \
        libxcb-xkb1 \
        libxcomposite1 \
        libxcursor1 \
        libxdamage1 \
        libxdmcp6 \
        libxext6 \
        libxfixes3 \
        libxi6 \
        libxkbcommon0 \
        libxkbcommon-x11-0 \
        libxrandr2 \
        libxrender1 \
        libxtst6 \
        zlib1g \
    && curl -fsSL \
        "https://github.com/git-lfs/git-lfs/releases/download/v${GIT_LFS_VERSION}/git-lfs-linux-amd64-v${GIT_LFS_VERSION}.tar.gz" \
        -o /tmp/git-lfs.tar.gz \
    && tar -xzf /tmp/git-lfs.tar.gz -C /tmp \
    && install -m 0755 "/tmp/git-lfs-${GIT_LFS_VERSION}/git-lfs" /usr/local/bin/git-lfs \
    && rm -rf /tmp/git-lfs.tar.gz "/tmp/git-lfs-${GIT_LFS_VERSION}" \
    && git lfs install --system \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
