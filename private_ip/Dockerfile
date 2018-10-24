FROM openjdk:8-jre-alpine

# Install required packages
RUN apk add --no-cache \
    bash \
    su-exec

ENV ZOO_USER=zookeeper \
    ZOO_CONF_DIR=/opt/zookeeper/conf \
    ZOO_DATA_DIR=/opt/zookeeper/data \
    ZOO_DATA_LOG_DIR=/opt/zookeeper/datalog \
    ZOO_APP_LOGS_DIR=/opt/zookeeper/logs \
    ZOO_PORT=2181 \
    ZOO_TICK_TIME=2000 \
    ZOO_INIT_LIMIT=60 \
    ZOO_SYNC_LIMIT=50 \
    ZOO_MAX_CLIENT_CNXNS=60

# Add a user and make dirs
RUN set -ex; \
    adduser -D "$ZOO_USER"; \
    mkdir -p "$ZOO_DATA_LOG_DIR" "$ZOO_DATA_DIR"; \
    chown "$ZOO_USER:$ZOO_USER" "$ZOO_DATA_LOG_DIR" "$ZOO_DATA_DIR"

RUN set -ex; \
    mkdir -p "$ZOO_CONF_DIR" "$ZOO_APP_LOGS_DIR"; \
    chown "$ZOO_USER:$ZOO_USER" "$ZOO_CONF_DIR" "$ZOO_APP_LOGS_DIR"

ARG GPG_KEY=D0BC8D8A4E90A40AFDFC43B3E22A746A68E327C1
ARG DISTRO_NAME=zookeeper-3.4.11

# Download Apache Zookeeper, verify its PGP signature, untar and clean up
RUN set -ex; \
    apk add --no-cache --virtual .build-deps \
        ca-certificates \
        gnupg \
        libressl; \
    wget -q "https://archive.apache.org/dist/zookeeper/$DISTRO_NAME/$DISTRO_NAME.tar.gz"; \
    wget -q "https://archive.apache.org/dist/zookeeper/$DISTRO_NAME/$DISTRO_NAME.tar.gz.asc"; \
    export GNUPGHOME="$(mktemp -d)"; \
    gpg --keyserver ha.pool.sks-keyservers.net --recv-key "$GPG_KEY" || \
    gpg --keyserver pgp.mit.edu --recv-keys "$GPG_KEY" || \
    gpg --keyserver keyserver.pgp.com --recv-keys "$GPG_KEY"; \
    gpg --batch --verify "$DISTRO_NAME.tar.gz.asc" "$DISTRO_NAME.tar.gz"; \
    tar -xzf "$DISTRO_NAME.tar.gz"; \
    mv "$DISTRO_NAME/conf/"* "$ZOO_CONF_DIR"; \
    rm -rf "$GNUPGHOME" "$DISTRO_NAME.tar.gz" "$DISTRO_NAME.tar.gz.asc"; \
    apk del .build-deps

# Install python
RUN apk add  --update python python-dev py-pip

# Install python dependencies
RUN pip install boto3 \
    && pip install argparse \
    && pip install awscli --upgrade --user

WORKDIR $DISTRO_NAME
VOLUME ["$ZOO_DATA_DIR", "$ZOO_DATA_LOG_DIR"]

# prepare automation file
RUN mkdir -p /pyscripts
ADD automation.py /pyscripts

RUN mkdir -p /ecs/data/zookeeper/data

RUN mkdir -p /ecs/data/zookeeper/conf
ADD zoo.cfg /ecs/data/zookeeper/conf

RUN chmod -R 777 /ecs/data/zookeeper

#### poter-jmx install
ARG PORTER_JMX_VERSION
RUN mkdir /opt/porter-jmx
COPY porter-jmx-${PORTER_JMX_VERSION}-javaagent.jar /opt/porter-jmx/porter-jmx-javaagent.jar

# log4j configuration
COPY log4j.properties "$ZOO_CONF_DIR"

# override zkServer.sh
COPY zkServer.sh /$DISTRO_NAME/bin

EXPOSE $ZOO_PORT 2888 3888

ENV PATH=$PATH:/$DISTRO_NAME/bin \
    ZOOCFGDIR=$ZOO_CONF_DIR

COPY docker-entrypoint.sh /
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["zkServer.sh", "start-foreground"]
