FROM ubuntu:22.04

ENV HOME=/home/zoomrec \
    START_DIR=/start \
    DEBIAN_FRONTEND=noninteractive

# Add user
RUN useradd -ms /bin/bash zoomrec -d ${HOME}
WORKDIR ${HOME}

ADD res/requirements.txt ${HOME}/res/requirements.txt
#ADD res/install/ ${HOME}/res/install/

# Install some tools
RUN apt-get update && \
    apt-get install --no-install-recommends --no-install-suggests -y \
    apt \
    apt-utils \
    ca-certificates \
    publicsuffix \
    libapt-pkg6.0 \
    libpsl5 \
    libssl3 \
    libnss3 \
    openssl \
    wget \
    locales \
    bzip2 \
    tzdata \ 
    gcc \
    make \
    scrot && \
    # Generate locales for en_US.UTF-8
    locale-gen en_US.UTF-8

# Install tigervnc
RUN wget -q -O ${HOME}/res/tigervnc-1.10.0.x86_64.tar.gz https://sourceforge.net/projects/tigervnc/files/stable/1.10.0/tigervnc-1.10.0.x86_64.tar.gz && \
    tar xz -f ${HOME}/res/tigervnc-1.10.0.x86_64.tar.gz --strip 1 -C / && \
    rm -rf ${HOME}/res/tigervnc-1.10.0.x86_64.tar.gz

# Install xfce ui
RUN apt-get update && \
    apt-get install --no-install-recommends --no-install-suggests -y \
    supervisor \
    xfce4 \
    xfce4-terminal

# Install alsa
RUN apt-get update && \
    apt-get install --no-install-recommends --no-install-suggests -y \
    alsa-base \
    alsa-utils \
    libsndfile1-dev \
    libasound2-dev \
    libasound2-plugins \
    # Install alsa-plugins
    gcc \
    make \
    build-essential \
    file && \
    wget -q -O ${HOME}/res/alsa-plugins-1.2.7.1.tar.bz2 https://www.alsa-project.org/files/pub/plugins/alsa-plugins-1.2.7.1.tar.bz2 && \
    tar xf ${HOME}/res/alsa-plugins-1.2.7.1.tar.bz2 -C ${HOME}/res/ && \
    sh ${HOME}/res/alsa-plugins-1.2.7.1/configure --sysconfdir=/etc && \
    make install && \
    rm -rf ${HOME}/res/alsa-plugins-1.2.7.1.tar.bz2 ${HOME}/res/alsa-plugins-1.2.7.1

# Install pulseaudio
RUN apt-get update && \
    apt-get install --no-install-recommends --no-install-suggests -y \
    pulseaudio \
    pavucontrol

# Install necessary packages
RUN apt-get update && \
    apt-get install --no-install-recommends --no-install-suggests -y \
    ibus \
    dbus-user-session \
    dbus-x11 \
    dbus \
    at-spi2-core \
    xauth \
    x11-xserver-utils \
    libxkbcommon-x11-0 \
    xdg-utils

# Install Zoom dependencies
RUN apt-get update && \
    apt-get install --no-install-recommends --no-install-suggests -y \
    libxcb-xinerama0 \
    libglib2.0-0 \
    libxcb-shape0 \
    libxcb-shm0 \
    libxcb-xfixes0 \
    libxcb-randr0 \
    libxcb-image0 \
    libfontconfig1 \
    libgl1-mesa-glx \
    libegl1-mesa \
    libxi6 \
    libsm6 \
    libxrender1 \
    libpulse0 \
    libxcomposite1 \
    libxslt1.1 \
    libsqlite3-0 \
    libxcb-keysyms1 \
    libxcb-xtest0 && \
    # Install Zoom
    wget -q -O zoom_amd64.deb https://zoom.us/client/latest/zoom_amd64.deb && \
    dpkg -i zoom_amd64.deb && \
    apt-get -f install -y && \
    rm -rf zoom_amd64.deb

# Install FFmpeg
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    ffmpeg \
    libavcodec-extra

# Install Python
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    python3 \
    python3-pip \
    python3-tk \
    python3-dev \
    python3-setuptools

# Install Python dependencies
RUN pip3 install --upgrade --no-cache-dir -r ${HOME}/res/requirements.txt

# Clean up
RUN apt-get autoremove --purge -y && \
    apt-get autoclean -y && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/*

# Allow access to pulseaudio and alsa
RUN adduser zoomrec pulse-access && \
    adduser zoomrec audio

USER zoomrec

# Add home resources
ADD res/home/ ${HOME}/

# Add startup
ADD res/entrypoint.sh ${START_DIR}/entrypoint.sh
ADD res/xfce.sh ${START_DIR}/xfce.sh

# Add python script with resources
ADD zoomrec.py ${HOME}/
ADD res/img ${HOME}/img

USER 0

# Disable panel
RUN echo "#!/bin/bash \nexit 1" > /usr/bin/xfce4-panel

# Set permissions
RUN chmod a+x ${START_DIR}/entrypoint.sh && \
    chmod -R a+rw ${START_DIR} && \
    chown -R zoomrec:zoomrec ${HOME} && \
    find ${HOME}/ -name '*.sh' -exec chmod -v a+x {} + && \
    find ${HOME}/ -name '*.desktop' -exec chmod -v a+x {} +


ENV TZ=Europe/Berlin \
    TERM=xfce4-terminal \
    VNC_RESOLUTION=1280x720 \
    VNC_COL_DEPTH=24 \
    VNC_PW=zoomrec \
    VNC_PORT=5901 \
    DISPLAY=:1 \
    GTK_IM_MODULE=ibus \
    XDG_RUNTIME_DIR=/tmp/runtime-zoomrec

EXPOSE ${VNC_PORT}
USER zoomrec
CMD ${START_DIR}/entrypoint.sh