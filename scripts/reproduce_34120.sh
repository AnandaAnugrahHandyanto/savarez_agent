#!/usr/bin/env bash
#
# Reproduction script for cronjob "schedule is required for create" bug
# Issue: #34120
#
# Demonstrates:
#   1) Schema before sanitization (has allOf with if/then/else)
#   2) Schema after sanitization (allOf stripped => model sees only required: ["action"])
#   3) Call fails without schedule (what the bug reporter experienced)
#   4) Call succeeds with schedule (when the model knows to include it)
#
set -euo pipefail
cd "$(dirname "$0")/.."  # hermes-agent root

# Activate venv
if [ -d .venv ]; then
    source .venv/bin/activate
elif [ -d venv ]; then
    source venv/bin/activate
fi

echo "=== Step 1: Run the reproduction Python script ==="
python -c "
import sys, json, copy
sys.path.insert(0, '.')

from tools.cronjob_tools import CRONJOB_SCHEMA
params = CRONJOB_SCHEMA['parameters']

print('BEFORE SANITIZATION:')
print(f'  allOf present: {\"allOf\" in params}')
print(f'  required: {params[\"required\"]}')
print()

from tools.schema_sanitizer import sanitize_tool_schemas
tool = {'type': 'function', 'function': {'name': 'cronjob', 'parameters': params}}
sanitized = sanitize_tool_schemas([copy.deepcopy(tool)])[0]['function']['parameters']

print('AFTER SANITIZATION:')
print(f'  allOf present: {\"allOf\" in sanitized}')
print(f'  required: {sanitized[\"required\"]}')
print()
print('=> Root cause: allOf is stripped. Model sees only required=[\"action\"].')
print()

print('CALL WITHOUT SCHEDULE:')
from tools.cronjob_tools import cronjob
r1 = cronjob(action='create')
print(f'  {json.dumps(r1)}')
print()

print('CALL WITH SCHEDULE:')
r2 = cronjob(action='create', schedule='every 5m', prompt='echo hello', name='repro-test')
print(f'  success: {json.loads(r2)[\"success\"]}') if isinstance(r2, str) else print(f'  success: {r2[\"success\"]}')
if not isinstance(r2, str) and r2.get('success'):
    jid = r2['output']['job_id']
    from cron.jobs import remove_job
    remove_job(jid)
    print(f'  Cleanup: removed job {jid}')
"

echo ""
echo "=== Step 2: Run relevant tests ==="
python -m pytest tests/tools/test_cronjob_tools.py -q --tb=short
