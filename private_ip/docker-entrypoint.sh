#!/bin/bash

set -e

# Allow the container to be started with `--user`
if [[ "$1" = 'zkServer.sh' && "$(id -u)" = '0' ]]; then
    chown -R "$ZOO_USER" "$ZOO_DATA_DIR" "$ZOO_DATA_LOG_DIR" "$ZOO_CONF_DIR"
    exec su-exec "$ZOO_USER" "$0" "$@"
fi

# start fjord zookeeper automation
echo "start fjord zookeeper automation ... "
python /pyscripts/automation.py

if [[ -f "$ZOO_DATA_DIR/myid" ]]; then
    rm $ZOO_DATA_DIR/myid
fi
echo "copying myid files to $ZOO_DATA_DIR"
cp /ecs/data/zookeeper/data/myid $ZOO_DATA_DIR/myid

if [[ -f "$ZOO_CONF_DIR/zoo.cfg" ]]; then
    rm $ZOO_CONF_DIR/zoo.cfg
fi    
echo "copying zoo.cfg files to $ZOO_CONF_DIR"
cp /ecs/data/zookeeper/conf/zoo.cfg $ZOO_CONF_DIR/zoo.cfg

# Generate the config only if it doesn't exist
if [[ ! -f "$ZOO_CONF_DIR/zoo.cfg" ]]; then
    CONFIG="$ZOO_CONF_DIR/zoo.cfg"

    echo "clientPort=$ZOO_PORT" >> "$CONFIG"
    echo "dataDir=$ZOO_DATA_DIR" >> "$CONFIG"
    echo "dataLogDir=$ZOO_DATA_LOG_DIR" >> "$CONFIG"

    echo "tickTime=$ZOO_TICK_TIME" >> "$CONFIG"
    echo "initLimit=$ZOO_INIT_LIMIT" >> "$CONFIG"
    echo "syncLimit=$ZOO_SYNC_LIMIT" >> "$CONFIG"

    echo "maxClientCnxns=$ZOO_MAX_CLIENT_CNXNS" >> "$CONFIG"

    for server in $ZOO_SERVERS; do
        echo "$server" >> "$CONFIG"
    done
fi

# Write myid only if it doesn't exist
if [[ ! -f "$ZOO_DATA_DIR/myid" ]]; then
    echo "${ZOO_MY_ID:-1}" > "$ZOO_DATA_DIR/myid"
fi



exec "$@"
