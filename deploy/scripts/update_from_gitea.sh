#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
DEPLOY_TARGET_SHA="${DEPLOY_TARGET_SHA:-${DEPLOY_EXPECTED_SHA:-}}"
DEPLOY_REPOSITORY_URL="${DEPLOY_REPOSITORY_URL:-}"
DEPLOY_LOCAL_GITEA_HTTP_ORIGIN="${DEPLOY_LOCAL_GITEA_HTTP_ORIGIN:-}"
DEPLOY_LOCAL_GITEA_SSH_ORIGIN="${DEPLOY_LOCAL_GITEA_SSH_ORIGIN:-}"
COMPOSE_FILE="${COMPOSE_FILE:-${APP_DIR}/compose.yaml}"
ENV_FILE="${ENV_FILE:-${APP_DIR}/.env}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/health}"
LOCK_FILE="${DEPLOY_LOCK_FILE:-${APP_DIR}/.deploy.lock}"
GIT_FETCH_ATTEMPTS="${DEPLOY_GIT_FETCH_ATTEMPTS:-3}"
GIT_FETCH_RETRY_SECONDS="${DEPLOY_GIT_FETCH_RETRY_SECONDS:-2}"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "Another deployment is already running; the latest push will be handled by its worker." >&2
  exit 0
fi

cd "${APP_DIR}"

if [[ ! -d .git ]]; then
  echo "Deployment directory is not a Git checkout: ${APP_DIR}" >&2
  exit 1
fi
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing runtime environment file: ${ENV_FILE}" >&2
  exit 1
fi

export GIT_TERMINAL_PROMPT=0

if ! [[ "${GIT_FETCH_ATTEMPTS}" =~ ^[1-5]$ ]]; then
  echo "DEPLOY_GIT_FETCH_ATTEMPTS must be an integer between 1 and 5." >&2
  exit 1
fi
if ! [[ "${GIT_FETCH_RETRY_SECONDS}" =~ ^[1-9][0-9]?$ ]] || (( GIT_FETCH_RETRY_SECONDS > 30 )); then
  echo "DEPLOY_GIT_FETCH_RETRY_SECONDS must be an integer between 1 and 30." >&2
  exit 1
fi

is_transient_fetch_failure() {
  grep -Eqi \
    "couldn't connect|connection reset|connection timed out|failure when receiving data from the peer|gnutls recv error|rpc failed|tls connection was non-properly terminated|remote end hung up unexpectedly|network is unreachable|temporary failure|timed out"
}

fetch_repository() {
  local remote="$1"
  local branch_ref="$2"
  local attempt=1
  local status=0
  local output=""

  while (( attempt <= GIT_FETCH_ATTEMPTS )); do
    if output="$(
      git -c http.version=HTTP/1.1 \
        -c http.lowSpeedLimit=1 \
        -c http.lowSpeedTime=120 \
        fetch --prune --no-tags "${remote}" \
        "+refs/heads/${DEPLOY_BRANCH}:${branch_ref}" \
        "+refs/tags/v*:refs/tags/v*" 2>&1
    )"; then
      [[ -z "${output}" ]] || printf '%s\n' "${output}"
      return 0
    else
      status=$?
    fi
    printf '%s\n' "${output}" >&2
    if (( attempt == GIT_FETCH_ATTEMPTS )) || ! printf '%s' "${output}" | is_transient_fetch_failure; then
      return "${status}"
    fi
    echo "Git fetch attempt ${attempt}/${GIT_FETCH_ATTEMPTS} failed; retrying in $(( GIT_FETCH_RETRY_SECONDS * attempt ))s." >&2
    sleep "$(( GIT_FETCH_RETRY_SECONDS * attempt ))"
    ((attempt += 1))
  done
}

fetch_remote_for_repository() {
  local repository_url="$1"
  local http_origin="${DEPLOY_LOCAL_GITEA_HTTP_ORIGIN%/}"
  local ssh_origin="${DEPLOY_LOCAL_GITEA_SSH_ORIGIN%/}"

  if [[ -z "${http_origin}" && -z "${ssh_origin}" ]]; then
    printf '%s\n' "${repository_url}"
    return 0
  fi
  if [[ -z "${http_origin}" || -z "${ssh_origin}" ]]; then
    echo "DEPLOY_LOCAL_GITEA_HTTP_ORIGIN and DEPLOY_LOCAL_GITEA_SSH_ORIGIN must be set together." >&2
    return 1
  fi
  if [[ "${repository_url}" == "${http_origin}/"* ]]; then
    printf '%s%s\n' "${ssh_origin}" "${repository_url#"${http_origin}"}"
    return 0
  fi
  printf '%s\n' "${repository_url}"
}

if [[ -n "${DEPLOY_REPOSITORY_URL}" ]]; then
  case "${DEPLOY_REPOSITORY_URL}" in
    https://*|http://*|ssh://*|*@*:*) ;;
    *)
      echo "Invalid deployment repository URL." >&2
      exit 1
      ;;
  esac
  echo "Fetching selected repository branch ${DEPLOY_BRANCH} ..."
  candidate_ref="refs/remotes/update-candidate/${DEPLOY_BRANCH}"
  fetch_remote="$(fetch_remote_for_repository "${DEPLOY_REPOSITORY_URL}")"
  fetch_repository "${fetch_remote}" "${candidate_ref}"
  remote_sha="$(git rev-parse "${candidate_ref}")"
  remote_label="${DEPLOY_REPOSITORY_URL}"
else
  echo "Fetching origin/${DEPLOY_BRANCH} ..."
  fetch_repository "origin" "refs/remotes/origin/${DEPLOY_BRANCH}"
  remote_sha="$(git rev-parse "origin/${DEPLOY_BRANCH}")"
  remote_label="origin/${DEPLOY_BRANCH}"
fi

target_sha="${DEPLOY_TARGET_SHA:-${remote_sha}}"
previous_sha="$(git rev-parse HEAD)"
if [[ ! "${target_sha}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Invalid deployment target SHA: ${target_sha}" >&2
  exit 1
fi
if ! git merge-base --is-ancestor "${target_sha}" "${remote_sha}"; then
  echo "Deployment target ${target_sha} is not in ${remote_label} history." >&2
  exit 1
fi
if [[ "${target_sha}" != "${remote_sha}" ]]; then
  echo "Deploying selected version ${target_sha}; ${remote_label} is ${remote_sha}."
fi

compose_args=(--env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")

wait_for_health() {
  for _ in {1..30}; do
    if curl --fail --silent --show-error --max-time 10 "${HEALTH_URL}" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

rollback_deployment() {
  local failure_status="$1"
  set +e
  trap - EXIT
  echo "Deployment failed; restoring commit ${previous_sha} ..." >&2
  git clean -fd
  git checkout -B "${DEPLOY_BRANCH}" "${previous_sha}"
  git reset --hard "${previous_sha}"
  docker compose "${compose_args[@]}" config --quiet
  if ! docker compose "${compose_args[@]}" build app; then
    echo "Rollback image build failed." >&2
  fi
  docker compose "${compose_args[@]}" up -d --wait --no-deps db
  docker compose "${compose_args[@]}" up -d --no-deps --remove-orphans app
  if ! wait_for_health; then
    echo "Rollback health check failed: ${HEALTH_URL}" >&2
    docker compose "${compose_args[@]}" ps >&2 || true
    docker compose "${compose_args[@]}" logs --tail=100 app db >&2 || true
  else
    echo "Rollback completed at commit ${previous_sha}." >&2
  fi
  exit "${failure_status}"
}

deployment_exit_handler() {
  local status="$?"
  if [[ "${status}" -ne 0 ]]; then
    rollback_deployment "${status}"
  fi
}

trap deployment_exit_handler EXIT

# This directory is a dedicated deployment checkout. Keep ignored runtime files
# such as .env and backups, but remove untracked source files from bootstrapping.
git clean -fd
git checkout -B "${DEPLOY_BRANCH}" "${target_sha}"
git reset --hard "${target_sha}"

docker compose "${compose_args[@]}" config --quiet

echo "Building the application and migration images ..."
docker compose "${compose_args[@]}" build --pull app migrate

echo "Ensuring the database service is healthy ..."
docker compose "${compose_args[@]}" up -d --wait --no-deps db

echo "Stopping the previous application before database migration ..."
docker compose "${compose_args[@]}" stop app || true

echo "Running tracked database migrations ..."
if ! docker compose "${compose_args[@]}" run --rm --no-deps -T migrate; then
  echo "Tracked migration failed. Migration output is retained in the deployment service journal." >&2
  docker compose "${compose_args[@]}" ps >&2 || true
  exit 1
fi

echo "Starting the application service ..."
docker compose "${compose_args[@]}" up -d --no-deps --remove-orphans app

echo "Checking ${HEALTH_URL} ..."
if ! wait_for_health; then
  echo "Health check failed: ${HEALTH_URL}" >&2
  docker compose "${compose_args[@]}" ps >&2 || true
  docker compose "${compose_args[@]}" logs --tail=100 app db >&2 || true
  exit 1
fi

echo "Published commit: $(git rev-parse --short HEAD)"
