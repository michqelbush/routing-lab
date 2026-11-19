#!/usr/bin/env bash
# Rebuild every router config from inventory.yml, redeploy the lab, and verify it
set -euo pipefail
cd "$(dirname "$0")"

.venv/bin/python generate.py
containerlab deploy -t lab.clab.yml --reconfigure
.venv/bin/python verify.py
