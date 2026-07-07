#!/bin/sh
set -eu

JOB_NAME="${JOB_NAME:-batch-embed-logseq}"

kubectl delete job "$JOB_NAME" --ignore-not-found=true

echo "Deleted job $JOB_NAME. EKS Auto Mode should remove idle worker nodes after its consolidation delay."
echo "The EKS control plane is still running and still costs money; use deploy/delete-cluster.sh to stop that cost."
echo
kubectl get jobs,pods,nodes
