#!/bin/sh
set -eu

CLUSTER_CONFIG="${CLUSTER_CONFIG:-cluster.yaml}"
AWS_PROFILE="${AWS_PROFILE:-default}"
AWS_REGION="${AWS_REGION:-us-east-1}"

if command -v eksctl >/dev/null 2>&1; then
  eksctl create cluster -f "$CLUSTER_CONFIG"
else
  docker run \
    --rm -it \
    -v "$PWD":/configs \
    -v "$HOME/.aws":/root/.aws:ro \
    -e AWS_PROFILE="$AWS_PROFILE" \
    -e AWS_REGION="$AWS_REGION" \
    public.ecr.aws/eksctl/eksctl \
    create cluster -f "/configs/$CLUSTER_CONFIG"
fi
