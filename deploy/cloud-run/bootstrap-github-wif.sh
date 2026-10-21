#!/usr/bin/env bash
# Initial setup only. Review IAM scope and obtain approval before executing.
# On partial failure inspect existing resources before resuming individual steps.
set -euo pipefail

deployment_project="${1:?Pass the approved dedicated project ID}"
if [[ "$deployment_project" != "jhworks-staging-tykimdream" ]]; then
  printf 'Refusing a different project. Review this script before adapting it.\n' >&2
  exit 2
fi
deployment_number="$(gcloud projects describe "$deployment_project" --format='value(projectNumber)')"
if [[ "$deployment_number" != "968398406137" ]]; then exit 2; fi
policy_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
deployment_account="jhworks-deploy@${deployment_project}.iam.gserviceaccount.com"
federation_pool="jhworks-github"
federation_provider="github-main-staging"

attribute_mapping="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(",".join(k+"="+v for k,v in d["attribute_mapping"].items()))' "$policy_directory/wif-staging.json")"
attribute_condition="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["attribute_condition"])' "$policy_directory/wif-staging.json")"

gcloud iam roles create jhworksStagingDeployer \
  --project="$deployment_project" --file="$policy_directory/deployer-role.yaml"

gcloud iam workload-identity-pools create "$federation_pool" \
  --project="$deployment_project" --location=global --display-name='JHWorks GitHub staging'
gcloud iam workload-identity-pools providers create-oidc "$federation_provider" \
  --project="$deployment_project" --location=global --workload-identity-pool="$federation_pool" \
  --issuer-uri=https://token.actions.githubusercontent.com \
  --attribute-mapping="$attribute_mapping" --attribute-condition="$attribute_condition"

gcloud iam service-accounts add-iam-policy-binding "$deployment_account" \
  --project="$deployment_project" --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${deployment_number}/locations/global/workloadIdentityPools/${federation_pool}/attribute.repository_id/1341433132"

gcloud projects add-iam-policy-binding "$deployment_project" \
  --role="projects/${deployment_project}/roles/jhworksStagingDeployer" \
  --member="serviceAccount:${deployment_account}" --condition=None

gcloud artifacts repositories add-iam-policy-binding jhworks \
  --project="$deployment_project" --location=asia-northeast3 \
  --role=roles/artifactregistry.writer --member="serviceAccount:${deployment_account}"

for execution_account in jhworks-runtime jhworks-migrate; do
  gcloud iam service-accounts add-iam-policy-binding \
    "${execution_account}@${deployment_project}.iam.gserviceaccount.com" \
    --project="$deployment_project" --role=roles/iam.serviceAccountUser \
    --member="serviceAccount:${deployment_account}"
done
