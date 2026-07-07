set shell := ["sh", "-cu"]

image := "logseq-semantic-search"

default:
    just --list

check-env:
    test -n "${AWS_ACCOUNT_ID:-}" || { echo "AWS_ACCOUNT_ID must be set" >&2; exit 1; }
    test -n "${AWS_REGION:-}" || { echo "AWS_REGION must be set" >&2; exit 1; }
    test -n "${DOCKER_TAG:-}" || { echo "DOCKER_TAG must be set" >&2; exit 1; }

build:
    DOCKER_BUILDKIT=1 docker build \
      --build-context qwen_model="${QWEN_MODEL_CACHE:-$HOME/.cache/huggingface/hub/models--Qwen--Qwen3-Embedding-0.6B}" \
      -t {{image}}:local .

tag: check-env
    docker tag {{image}}:local {{image}}:$DOCKER_TAG
    docker tag {{image}}:$DOCKER_TAG ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/{{image}}:$DOCKER_TAG

ecr-login: check-env
    aws ecr get-login-password --region "$AWS_REGION" | \
      docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

push: tag ecr-login
    docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/{{image}}:$DOCKER_TAG

publish: build push
