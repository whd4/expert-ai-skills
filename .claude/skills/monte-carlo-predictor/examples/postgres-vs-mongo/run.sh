#!/bin/bash
# Run the postgres-vs-mongo decision simulation.
#
# Usage:
#   ./run.sh                    # text report
#   ./run.sh --format json      # machine-readable
#   ./run.sh --charts ./out     # + matplotlib PNGs (requires matplotlib)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE/../.."  # cd to monte-carlo-predictor root so "engine" imports cleanly
python3 -m engine run "$HERE/spec.yaml" "$@"
