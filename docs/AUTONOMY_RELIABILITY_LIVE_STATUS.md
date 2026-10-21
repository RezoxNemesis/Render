# Render Studio 0.18 — bounded autonomous native execution

## Evidence and scope

The actual target is Render Studio (`com.rezox.render`) on Android. ChatGPT
uses the **existing VideoStudio MCP v3 → same-phone Binder** bridge. The other
VideoStudio app retains its credentials, projects, Gallery policy and timeline.
Only Render's typed native Blender bpy calls may count as 3D execution proof.
No Railway relay, cloud Blender, arbitrary Python, remote shell, Gallery read,
or operating-system privilege bypass is added.

## Eliminated or reduced reliability problems

1. **Unbounded incoming Binder work.** A single worker now has 12 pending slots
   with explicit rejection instead of an ever-growing queue while rendering.
   A rejected request has not run; it can be submitted again intentionally.
2. **Two native executor contention.** The separately started agent will resend
   journaled results but does not claim new relay jobs while the direct Binder
   bridge owns the process-wide native Blender lock.
3. **Invisible native operations.** An in-app animated hand and Android native
   work notification start only after Android accepts a journaled native job.
   The native source is explicit; notifications never imply GitHub coding is
   happening inside the phone.
4. **Fabricated or frozen progress.** Blender writes a small per-job progress
   record during actual animation rendering. The Android spool validates that
   job ID and displays the measured frame percentage. Unsupported operations
   show an indeterminate stage. Notification updates are throttled.
5. **Lost/native ambiguous receipts.** Errors to commit the durable result
   journal yield `recovery_required`, not a false success badge. Interrupted
   operations remain uncertain and are NEVER blindly retried.
6. **Phone sleep.** A bounded partial CPU wake lock is held only during a
   locally authorized Blender operation and released with try-with-resources.
   It helps keep CPU work progressing but cannot defeat background restrictions,
   GPU driver crashes, Android thermal/power limits or process termination.
7. **Operator stop.** The live notification offers a local, non-exported Stop
   receiver. It disables new bridge/session work and sets a cooperative cancel
   flag. Blender itself may still finish an uninterruptible operator.
8. **Unclear feature status.** `render.agent.diagnostics` is a read-only MCP
   action exposing executor status, native editor readiness, real work stage,
   notification availability, a journal history and the installed public
   signing fingerprint. No secret key, request payload or media path is exposed.
9. **Editor navigation stall.** Agent Control provides a direct owner-operated
   `OPEN BLENDER TO RESUME NATIVE JOBS` action. The Android OS can block
   background activity launches, so the agent never pretends it can force
   the native editor to the foreground from a sleeping phone.
10. **Ephemeral APK signatures.** CI push/PR builds are debug-only. A separate
    manual main-only protected-environment workflow uses the existing pinned
    owner-held keystore for release APKs after explicit review. It refuses to
    sign with an unexpected certificate.

## What cannot honestly be removed by code

- Android foreground-service start restrictions and POST_NOTIFICATIONS owner
  permission requirements, app process death, GPU/thermal limitations.
- Desktop GPU accelerators unsupported on the Android device.
- Native ffmpeg/H.264 if absent from the upstream bundled Blender build.
- A different installed APK signing certificate. Android refuses such an
  upgrade; back up and migrate deliberately or use safe side-by-side testing.
- A 100% autonomous tab-closing/system-wide hand without explicit Android
  accessibility permissions and verified, owner-controlled UI state.
  This upgrade's hand is an **in-app work indicator**, not remote Android touch.
- Production owner signing setup without a protected GitHub environment and
  owner's secure upload of the existing private key to environment secrets.

## Mandatory physical Android acceptance tests

1. In Render open Agent Control, verify the hand says idle and no ongoing work
   notification appears before a command.
2. Via VideoStudio MCP execute `render.agent.diagnostics`; verify Render app
   public ID, native executor status, installed signer and notification
   permissions. Ensure no other app claims Render execution.
3. With native Blender editor open, execute a Blender operation: hand animates,
   notification appears with the exact native action and stage; result is
   journaled and hand returns idle/completed.
4. Interrupt network/phone UI during a long command. Confirm no fabricated
   success, duplicate object or silent blind replay after resume.
5. Render frames on Android and confirm measured frame counts/progress or
   honest indeterminate status if Blender does not expose callbacks.
6. Tap Stop new commands. Verify further work is blocked locally and any
   unfinished native operator is treated as cooperative/uncertain.
7. Run a signed APK update only if the installed signer matches the pinned
   fingerprint and .blend backups have been exported.
8. Verify native video `video/mp4` content and playback from the user's
   Android Downloads and confirm Gallery access was never requested.

This document is a release checklist, not proof all steps passed. GitHub CI
can verify Java/Python/packaging; the phone must confirm real Blender execution.
