#!/bin/sh

COMMIT_HASH=$(git rev-parse --short HEAD)

# Tag is composed with zookeeper version and last commit.
BUILD_TAG=${BUILD_TAG:-"3.4.11-$COMMIT_HASH"}
PORTER_JMX_VERSION=${PORTER_JMX_VERSION:-"1.0.1"}

BUILD_DIR=$(dirname $0)

# Build the latest & specific tag version image.
docker build --build-arg PORTER_JMX_VERSION=$PORTER_JMX_VERSION \
             -t zuora/fjord-zookeeper:latest \
             -t zuora/fjord-zookeeper:$BUILD_TAG \
             $BUILD_DIR
