#!/usr/bin/env python3
"""One-time, owner-local setup of the EXISTING Render signing identity.

No private keystore/password is uploaded to ChatGPT or committed to Git.
Uses authenticated GitHub CLI and the owner's protected environment only.
"""
from __future__ import annotations
import argparse
import base64
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPO="RezoxNemesis/Render"
ENVIRONMENT="render-production"
EXPECTED=("03:01:F0:84:CB:37:45:7B:E8:23:53:A8:A0:7E:88:14:35:17:"
          "5B:FD:5B:F0:CF:EA:FA:2C:3D:D4:B2:5F:CF:57")
NAMES=(
    "RENDER_ANDROID_SIGNING_KEYSTORE_B64",
    "RENDER_ANDROID_SIGNING_STORE_PASSWORD",
    "RENDER_ANDROID_SIGNING_KEY_ALIAS",
    "RENDER_ANDROID_SIGNING_KEY_PASSWORD",
)


def run(args, *, value=None, environment=None):
    result=subprocess.run(args,input=value,capture_output=True,check=False,env=environment)
    if result.returncode:
        # Never output subprocess stderr: GitHub CLI or keytool might include
        # private paths or secret-derived information.
        raise RuntimeError("SETUP_STEP_FAILED: "+args[0])
    return result.stdout


def require_protected_environment():
    raw=run(["gh","api",f"repos/{REPO}/environments/{ENVIRONMENT}"])
    info=json.loads(raw)
    if info.get("name")!=ENVIRONMENT:
        raise RuntimeError("RENDER_PRODUCTION_ENVIRONMENT_NOT_FOUND")
    reviewers=any(rule.get("type")=="required_reviewers"
                  for rule in info.get("protection_rules",[]))
    policy=info.get("deployment_branch_policy") or {}
    restricts_branches=bool(policy.get("protected_branches") or
                             policy.get("custom_branch_policies"))
    if not (reviewers and restricts_branches):
        raise RuntimeError("PROTECT_PRODUCTION_ENVIRONMENT_WITH_MAIN_RULE_AND_REVIEWER")
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keystore",type=Path,required=True,
                        help="Private Render_Studio_Release_2026.p12")
    parser.add_argument("--alias",default="render-studio")
    args=parser.parse_args()
    if not args.keystore.is_file() or args.keystore.stat().st_size<1000:
        raise RuntimeError("OWNER_KEYSTORE_MISSING")
    if not shutil.which("gh") or not shutil.which("keytool"):
        raise RuntimeError("REQUIRES_AUTHENTICATED_GH_CLI_AND_JDK_KEYTOOL")

    password=getpass.getpass("Existing Render keystore password (not displayed): ")
    if not password:raise RuntimeError("OWNER_PASSWORD_MISSING")
    local_env=os.environ.copy()
    local_env["RENDER_OWNER_LOCAL_KEY_PASSWORD"]=password
    certificate=run([
        "keytool","-list","-v","-storetype","PKCS12",
        "-keystore",str(args.keystore),
        "-storepass:env","RENDER_OWNER_LOCAL_KEY_PASSWORD",
        "-alias",args.alias
    ],environment=local_env).decode("utf-8","replace")
    if EXPECTED not in certificate:
        raise RuntimeError("CERTIFICATE_FINGERPRINT_MISMATCH_ABORT")
    print("Verified existing permanent Render release signer SHA-256.")
    require_protected_environment()

    secret_bytes=args.keystore.read_bytes()
    entries=(
        base64.b64encode(secret_bytes),
        password.encode("utf-8"),
        args.alias.encode("utf-8"),
        password.encode("utf-8")
    )
    for name,value in zip(NAMES,entries):
        run(["gh","secret","set",name,"-R",REPO,"-e",ENVIRONMENT],
            value=value+b"\n")
        print("Stored protected environment secret:",name)
    print("Protected Render signer configured. Keep your separate offline backup.")
    print("Only the main-branch manual workflow may use this certificate.")


if __name__=="__main__":
    try:main()
    except Exception as error:
        print("Signing setup failed:",str(error),file=sys.stderr)
        sys.exit(1)
