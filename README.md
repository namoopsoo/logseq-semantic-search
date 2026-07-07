# logseq-semantic-search

This repo defines a docker container, which embeds markdown notes, like logseq markdown notes for example, and then serves search against them.

Embedding can be done in one shot if you have a fast host machine, or it can be done in shards over a kubernetes cluster, otherwise, reading and writing against blob storage like S3. Final embeddings get stored on a vector db like chromadb and served by the same docker container, with fast api.

# Installing
TBD

# Running
Locally, run the fast api app with,

```
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```


## Supporting EKS cluster
Build it
```sh

docker run \
  --rm -it \
  -v "$PWD":/configs \
  -v "$HOME/.aws":/root/.aws:ro \
  -e AWS_PROFILE="${AWS_PROFILE:-default}" \
  -e AWS_REGION="${AWS_REGION:-us-east-1}" \
  public.ecr.aws/eksctl/eksctl \
  create cluster -f /configs/cluster.yaml
```

## run docker locally

```sh
docker run \
  --rm -it \
  -p 8000:8000 \
  -v "$LOGSEQ_DIR:/notes:ro" \
  -v "$PWD/chroma_logseq:/chroma_logseq" \
  -v "$HOME/.cache/huggingface/hub:/models:ro" \
  -v "$PWD/local_embeddings:/local_embeddings" \
  -v "$PWD/encrypted_notes_dir:/encrypted_notes_dir" \
  -e LOGSEQ_DIR=/notes \
  -e LOCAL_ENCRYPTED_NOTES_DIR=/encrypted_notes_dir \
  -e DB_DIR=/chroma \
  -e LOCAL_EMBEDDINGS_DIR="/local_embeddings" \
  -e COLLECTION=logseq_notes \
  -e MODEL_NAME=Qwen/Qwen3-Embedding-0.6B\
  -e MARKDOWN_SOURCE="local" \
  -e HF_CACHE_DIR="/models" \
  -e WRITE_TO_S3="no" \
  -e WRITE_TO_CHROMA="no" \
  -e WRITE_TO_LOCAL="yes" \
  -e S3_BUCKET="no_bucket_specified" \
  -e LOCAL_MARKDOWN_GLOBS="2025_01_*.md" \
  -e S3_ENCRYPTION_KEY=$S3_ENCRYPTION_KEY \
  logseq-semantic-search:local bash
```


## Setup EKS secrets
create/edit, by setting as environmntal vars then running
```sh
kubernetes_secrets_group="logseq-batch-embed-env"

kubectl create secret generic $kubernetes_secrets_group \
  --from-literal=AWS_REGION=$AWS_REGION \
  --from-literal=S3_BUCKET=$S3_BUCKET \
  --from-literal=S3_ENCRYPTION_KEY=$S3_ENCRYPTION_KEY \

```
, editing, by first deleting, , and then creating again 
```
kubectl delete secret $kubernetes_secrets_group
```

## Build Docker Image with Local Qwen Cache

This build uses BuildKit to mount the local Hugging Face model cache as a named build context, without adding the 1.1GB model directory to the repo. The model cache directory must already exist locally.

```sh
DOCKER_BUILDKIT=1 docker build \
  --build-context qwen_model="$HOME/.cache/huggingface/hub/models--Qwen--Qwen3-Embedding-0.6B" \
  -t logseq-semantic-search:local .
```

## Apply Batch Embed Job

`kubectl apply -f` does not expand shell variables in Kubernetes YAML. Use allowlisted `envsubst` so only image/deploy variables are substituted, while Kubernetes runtime variables like `JOB_COMPLETION_INDEX` stay intact.

```sh
envsubst '$AWS_ACCOUNT_ID $AWS_REGION $DOCKER_TAG' < deploy/batch-embed.yaml | kubectl apply -f -
```

To preview the rendered manifest before applying it:

```sh
envsubst '$AWS_ACCOUNT_ID $AWS_REGION $DOCKER_TAG' < deploy/batch-embed.yaml
```

## EKS Pod Identity S3 Permissions

The batch embed job uses `serviceAccountName: logseq-embed-sa`, which should be associated with the IAM role `logseq-embed-s3-role` through EKS Pod Identity. Attach the S3 policy after setting `S3_BUCKET`:

```sh
envsubst '$S3_BUCKET' < deploy/logseq-embed-s3-policy.json | \
  aws iam put-role-policy \
    --role-name logseq-embed-s3-role \
    --policy-name logseq-embed-s3-access \
    --policy-document file:///dev/stdin
```

The policy grants `s3:ListBucket` for `ListObjectsV2`, `s3:GetObject` for reading markdown files, and `s3:PutObject` for writing embedding shards.
