"""Fail-closed audit for the OMEGA 13-source integration candidate, not a phase PR.

The only alternative to phase-owned paths is a short and explicit list of
integrator-only CI/version/tests. Never permit editing the frozen blueprint.
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_phase10_ownership import violations, RULES, SEED

INTEGRATOR_ONLY = frozenset((
    ".github/workflows/omega-combined-qa.yml",
    "tools/test_thermal_drive_inplace_contract.py",
    "tools/omega/test_omega_integrated_ownership.py",
))

def check(paths):
    bad=[]
    for path in paths:
        if path=="docs/omega/RENDER_OMEGA_TEN_PHASE_MASTER_BLUEPRINT.md":
            bad.append(path)
        elif path in INTEGRATOR_ONLY:
            continue
        elif not any(not violations(n,[path]) for n in RULES):
            bad.append(path)
    return bad

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--base",required=True)
    p.add_argument("--head",required=True)
    a=p.parse_args()
    if not all(re.fullmatch(r"[a-f0-9]{40}",x) for x in (a.base,a.head)):
        p.error("exact 40-char commit hashes required")
    subprocess.run(["git","merge-base","--is-ancestor",SEED,a.head],check=True)
    paths=subprocess.check_output(["git","diff","--name-only","-z",a.base,a.head]).split(b"\x00")
    changed=[s.decode() for s in paths if s]
    invalid=check(changed)
    print("OMEGA_13_INTEGRATION_OWNERSHIP",len(changed),"changed",invalid)
    if invalid:
        raise SystemExit("UNOWNED_INTEGRATION_FILES: "+", ".join(invalid))
if __name__=="__main__":
    main()
