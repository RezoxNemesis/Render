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
