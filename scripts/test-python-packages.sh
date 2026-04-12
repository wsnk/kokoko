#!/bin/bash
set -eo pipefail

function log() { echo "$*" >&2 ; }

if [[ "$GITHUB_ACTIONS" == "true" ]]; then
    function start-group() { log "::group::$*" ; }
    function end-group() { log "::endgroup::" ; }
else
    function start-group() { log "=== $* ===" ; }
    function end-group() { : ; }
fi


REPO_ROOT="$(git rev-parse --show-toplevel)"

function test_package()
{
    local pkg_dir="$1"
    local fails=""

    start-group "🧪 Testing package '$pkg_dir'"

    bash -c "cd '$pkg_dir' && uv sync" || fails+="sync "
    bash -c "cd '$pkg_dir' && uv run ruff check" || fails+="style "
    bash -c "cd '$pkg_dir' && uv run pytest -v" || fails+="tests "

    end-group

    if [[ -n "$fails" ]]; then
        log "    ❌ '$pkg_dir' - tests failed: $fails"
        return 1
    else
        log "    ✅ '$pkg_dir' - all tests passed"
    fi
}


cd "$REPO_ROOT/python"

FAILED=0
for pkg in ./*; do
    if [[ ! -d "$pkg" || ! -f "$pkg/pyproject.toml" ]]; then
        log "Skipping '$pkg' - not a package directory"
        continue
    fi
    log "Running tests for '$pkg'..."
    test_package "$pkg" || FAILED=1
done

if [[ $FAILED -ne 0 ]]; then
    log "Some tests failed"
    exit 1
else
    log "All tests passed successfully"
fi

