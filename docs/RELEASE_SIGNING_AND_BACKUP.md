# Render Studio — permanent Android APK signing and safe upgrades

## Private signing identity
The owner-held Android APK signing key was created OUTSIDE GitHub and is kept in private ChatGPT Library:
- /Render/Signing/Render_Studio_Release_2026.p12
- /Render/Signing/RENDER_RELEASE_KEY_RECOVERY_KEEP_PRIVATE.txt
- /Render/Signing/Render_Release_Certificate_Fingerprint.txt

Release signer: Render Studio, RSA-4096; SHA-256 CERTIFICATE fingerprint:
03:01:F0:84:CB:37:45:7B:E8:23:53:A8:A0:7E:88:14:35:17:5B:FD:5B:F0:CF:EA:FA:2C:3D:D4:B2:5F:CF:57

The fingerprint is public. The .p12 and recovery password are PRIVATE.
Never commit/upload either to the public repository, embed in APK assets,
print in CI logs or expose in screenshots or messages. Keep a separate encrypted backup.
Future app updates MUST use the same private key and package ID.

## One-time protected GitHub Actions secrets setup
Go to github.com/RezoxNemesis/Render -> Settings -> Secrets and variables ->
Actions -> Repository secrets, and set:
- RENDER_ANDROID_SIGNING_KEYSTORE_B64 : base64 of full .p12, without line breaks
- RENDER_ANDROID_SIGNING_STORE_PASSWORD : read only from PRIVATE recovery file
- RENDER_ANDROID_SIGNING_KEY_ALIAS : render-studio
- RENDER_ANDROID_SIGNING_KEY_PASSWORD : same private password

The connected GitHub tool lacks permission/actions for adding Secrets. These
values have NOT been configured, and the current CI artifacts remain
development debug builds. Do not call an unsigned/temporary-debug build a
permanently release-signed APK.

Full APK workflow builds debug by default. When all owner-protected signing
secrets are configured, it also executes assembleRelease with a stable
PKCS12 certificate, verifies the exact public SHA-256 signer fingerprint
and uploads a separate owner-signed release APK artifact.
Gradle release signing fails closed when any required input is absent.
CI removes its temporary keystore at the end of the workflow.

## Back up before the initial signing migration
Earlier GitHub Actions builds used per-run debug signing certificates.
Android refuses updating such an install with a DIFFERENT release signer,
even though the package name and APK architecture are identical.
Back up imported .blend projects BEFORE uninstalling any debug build:
1. Render -> Project Inspector -> BACK UP SAVED .BLEND PROJECTS.
2. Select an Android Files/Downloads or Drive destination outside the app.
3. Confirm ZIP contains saved project files and the SHA-256 manifest.
4. Separately back up linked textures, models and external library assets.
5. Only then migrate to the first owner-signed release APK.

Uninstalling Android applications can delete app-owned project data and
encrypted device credentials. Later updates signed by the SAME permanent
release certificate can install over previous release APKs, retaining
app data under normal Android conditions.

Current signing proof: JDK keytool creation and fingerprint verification.
Current missing proof: protected CI secrets, completed assembleRelease,
apksigner certificate check and physical-device update over a matching
older release APK. No existing installed APK signing identity was inspected.

## Non-destructive side-by-side installer
For a previous `com.rezox.render` APK whose debug certificate cannot be matched, build the `-PrenderSideBySide=true` variant. Android installs this variant as `com.rezox.render.preview`, independently of the original app: it does not uninstall, overwrite or migrate the original app-owned files, and it has its own Android Keystore identity. This is a safe test path while keeping existing projects. The original `com.rezox.render` package remains the production upgrade identity. VideoStudio Binder companion must explicitly support the preview package to route direct native commands. Never falsely claim the preview shares the original app data or automatically fixes all compatibility problems.

## v0.18: permanent signing with a protected, owner-reviewed release environment

**The existing RSA-4096 release identity is the permanent key. Do not regenerate it.**
The certificate and recovery data already exist in the user's **private ChatGPT
Library** under `/Render/Signing/`. The public fingerprint above remains pinned.
No private key or password is included in Git history, Android assets, PR
comments, screenshots, or public GitHub Actions artifacts.

The previous `full-native-apk.yml` workflow is now **debug-only**, even if
repository secrets exist. Ordinary feature-branch push/PR runs MUST NOT access
the owner signing material. The new `.github/workflows/render-owner-release.yml`
is the only native-release signer: manual `workflow_dispatch`, **main branch
only**, using environment `render-production` with required reviewer approval.
Its first step refuses missing secrets and signer fingerprint mismatch before
staging the expensive native Blender binary. Later steps check the signed APK's
public certificate and Android package name. Signing secrets are used only
during the protected job and the ephemeral runner keystore is removed afterward.

### One-time GitHub environment configuration (owner-only)

1. In GitHub open `RezoxNemesis/Render → Settings → Environments`, create
   `render-production`. Require a reviewer/owner approval and restrict
   deployment to protected branches or a custom branch policy for `main`.
2. Create these **environment** secrets there (not repository variables or
   feature-branch secrets): `RENDER_ANDROID_SIGNING_KEYSTORE_B64`,
   `RENDER_ANDROID_SIGNING_STORE_PASSWORD`,
   `RENDER_ANDROID_SIGNING_KEY_ALIAS`, and
   `RENDER_ANDROID_SIGNING_KEY_PASSWORD`.
3. From a trusted computer that already has GitHub CLI authentication and
   Java `keytool`, securely materialize your privately held
   `Render_Studio_Release_2026.p12` from ChatGPT Library, then run:
   `python3 tools/configure_owner_signing.py --keystore /private/path/Render_Studio_Release_2026.p12`.
   This prompts locally for the existing recovery password, checks the pinned
   public fingerprint, refuses an unprotected GitHub environment, and sends
   values through `gh secret set` **standard input**, never arguments or logs.
   No command in ChatGPT can supply the secrets through this GitHub connection;
   current secret-writing permission is unavailable, so this final owner action
   is **not yet completed**.
4. After audited code is merged to `main`, select GitHub Actions →
   `Render Studio permanent owner-signed release` → Run workflow on `main`
   and approve the protected environment. The workflow produces a release APK
   signed by the same owner key after device-independent checks.

### Safe installed-app upgrade gate

Call `render.engine.status` on the installed native APK. Versions with this
upgrade include `installedSignerSha256` and `usesPermanentOwnerSigner`.
A matching owner certificate is evidence of the installed signing identity;
a different fingerprint means **do not attempt to overwrite that APK**.
Back up .blend project files, dependencies and connection state before any
migration. Android's signature requirement is a platform rule and cannot be
legally bypassed by ChatGPT, the MCP bridge, or a CI job.

**Status:** permanent key exists privately; source-code signing isolation and
protected release workflow are implemented; owner GitHub environment secrets,
a signed release artifact, and an Android package upgrade are still unverified.
