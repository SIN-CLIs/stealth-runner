# Plan SR-31: Flow Compiler FCTES — Production Promotion

## Overview
Get the Flow Compiler (FCTES) from "code exists but never tested" to "automatic production promotion working". Currently 0 flows promoted despite infrastructure being complete.

## Current State vs Target

```
CURRENT:                          TARGET:
compiler.py ✅ exists             compiler.py ✅ tested
tracker.py ✅ exists              tracker.py ✅ 10 runs → auto-promote
signing.py ✅ exists              signing.py ✅ signed flow verified
compiled/   ❌ EMPTY              compiled/ ✅ survey_heypiggy_v17XXXXXXXXX.py
opencode.json ❌ fake entry       opencode.json ✅ real compiled tools
```

## Step 1: Test Compiler Chain

```python
# test_compiler_chain.py
from app.core.tracker import record
from app.core.compiler import FlowCompiler, compile as compile_flow

compiler = FlowCompiler()

# Simulate 10 successful runs
for i in range(10):
    record("survey_heypiggy", "success_direct")

# Check status
status = compiler.get_status("survey_heypiggy")
print(f"Status: {status}")
# → expected: tier='production', run_count=10, can_promote=True

# Compile
tool_name = compile_flow("survey_heypiggy")
print(f"Compiled: {tool_name}")
# → expected: survey_heypiggy_v<TIMESTAMP>

# Verify
import os
compiled_dir = Path(__file__).parent.parent.parent / "app" / "flows" / "compiled"
files = list(compiled_dir.glob("survey_heypiggy_v*.py"))
print(f"Compiled files: {files}")
# → expected: 1 Python file

# Check signing
sig_files = list(compiled_dir.glob("*.sig"))
print(f"Signature files: {sig_files}")
```

## Step 2: Fix Fake opencode.json Entry

```bash
# Current: "survey_5_fragen_v1777929926": true  (fake)
# Remove or replace with real compiled tool

python3 -c "
import json
with open('opencode.json') as f:
    config = json.load(f)
# Remove fake tool
config['tools'].pop('survey_5_fragen_v1777929926', None)
# Add real tool (after compile)
# config['tools']['survey_heypiggy_v...'] = True
with open('opencode.json', 'w') as f:
    json.dump(config, f, indent=2)
"
```

## Step 3: End-to-End Promotion Test

```bash
# 1. Flow ausführen (10×)
for i in $(seq 1 10); do
    python3 run_survey.py
    # Muss CDP-Modul benutzen (SR-28)
done

# 2. Promotion checken
python3 -c "
from app.core.compiler import FlowCompiler
status = FlowCompiler().get_status('survey_heypiggy')
print(status)
# tier sollte 'production' sein
"

# 3. Compilieren
python3 -c "
from app.core.compiler import compile
tool = compile('survey_heypiggy')
print(f'Promoted to: {tool}')
"

# 4. Verifizieren
ls -la app/flows/compiled/
cat ~/.stealth/flow_lock.json
```

## Implementation
| Step | Task | Time |
|------|------|------|
| 1 | Test-Script für Compiler Chain | 30min |
| 2 | opencode.json bereinigen | 15min |
| 3 | 10× Test-Runs + Promotion | 1h (braucht SR-28) |
| 4 | Signing-Verifikation testen | 30min |
| 5 | Dokumentation updaten | 30min |
| **Total** | **(abhängig von SR-28)** | **~2.5h** |
