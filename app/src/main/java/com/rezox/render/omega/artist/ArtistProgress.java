package com.rezox.render.omega.artist;

import java.util.Objects;
import java.util.regex.Pattern;

/**
 * Phase-11-only immutable artist work state for the future P10/P03 UI adapter.
 * Does not synthesize finger events or modify existing shared overlays/bridges.
 * DONE is only reachable through observed native postconditions.
 */
public final class ArtistProgress {
    public enum State {
        QUEUED, EXECUTING, OBSERVED_RESULT, NEEDS_CORRECTION, PAUSED, FAILED, DONE
    }

    private static final Pattern JOB = Pattern.compile("[0-9a-f]{32}");
    private static final Pattern NAME = Pattern.compile("[A-Za-z][A-Za-z0-9_.-]{0,63}");
    private static final Pattern SHA = Pattern.compile("[0-9a-f]{64}");

    public final String jobId;
    public final String operation;
    public final String target;
    public final State state;
    public final String proof;
    public final String expectedPostcondition;
    public final String explanation;
    public final int verifiedVertexChanges;

    private ArtistProgress(String jobId, String operation, String target,
                           State state, String proof, String expectedPostcondition, String explanation, int verifiedVertexChanges) {
        this.jobId = jobId;
        this.operation = operation;
        this.target = target;
        this.state = state;
        this.proof = proof;
        this.expectedPostcondition = expectedPostcondition;
        this.explanation = explanation;
        this.verifiedVertexChanges = verifiedVertexChanges;
    }

    public static ArtistProgress queued(String jobId, String operation, String target, String expectedPostcondition) {
        if (jobId == null || !JOB.matcher(jobId).matches()) throw new IllegalArgumentException("INVALID_JOB_ID");
        if (!"omega.artist.execute_tool".equals(operation) &&
            !"omega.artist.inspect_ui".equals(operation)) throw new IllegalArgumentException("INVALID_OPERATION");
        if (target == null || !NAME.matcher(target).matches()) throw new IllegalArgumentException("INVALID_TARGET");
        if (!"selection_active".equals(expectedPostcondition) && !"mode_changed".equals(expectedPostcondition) &&
            !"evaluated_mesh_changed".equals(expectedPostcondition) && !"modifier_present".equals(expectedPostcondition) &&
            !"inspected_native_scene".equals(expectedPostcondition))
            throw new IllegalArgumentException("INVALID_POSTCONDITION");
        if (("omega.artist.inspect_ui".equals(operation)) != "inspected_native_scene".equals(expectedPostcondition))
            throw new IllegalArgumentException("POSTCONDITION_OPERATION_MISMATCH");
        return new ArtistProgress(jobId, operation, target, State.QUEUED, "", expectedPostcondition, "Not yet executed", 0);
    }

    public ArtistProgress executing(String actualNativeTarget) {
        requireState(State.QUEUED);
        if (!target.equals(actualNativeTarget)) throw new IllegalArgumentException("NATIVE_TARGET_MISMATCH");
        return copy(State.EXECUTING, "", "Native Blender accepted work on " + target, 0);
    }

    /** Read-back values must come from Blender, not an API-acceptance event. */
    public ArtistProgress observed(String actualNativeTarget, String proofType,
                                   String sourceRevision, String resultRevision,
                                   int changedVertexCount, boolean nativeVerified) {
        requireState(State.EXECUTING);
        if (!nativeVerified || !target.equals(actualNativeTarget) ||
            sourceRevision == null || resultRevision == null ||
            !SHA.matcher(sourceRevision).matches() || !SHA.matcher(resultRevision).matches() ||
            changedVertexCount < 0 ||
            (!"inspected_native_scene".equals(proofType) && sourceRevision.equals(resultRevision))) {
            throw new IllegalArgumentException("UNVERIFIED_NATIVE_RECEIPT");
        }
        if (!expectedPostcondition.equals(proofType)) {
            throw new IllegalArgumentException("UNSUPPORTED_POSTCONDITION");
        }
        if ("evaluated_mesh_changed".equals(proofType) && changedVertexCount == 0) {
            throw new IllegalArgumentException("NO_NATIVE_MESH_CHANGE");
        }
        return copy(State.OBSERVED_RESULT, proofType, "Verified native " + proofType + " on " + target,
                    changedVertexCount);
    }

    public ArtistProgress done() {
        requireState(State.OBSERVED_RESULT);
        return copy(State.DONE, proof, explanation, verifiedVertexChanges);
    }

    public ArtistProgress paused(String reason) {
        if (state != State.EXECUTING && state != State.QUEUED)
            throw new IllegalStateException("CANNOT_PAUSE_THIS_STAGE");
        return copy(State.PAUSED, proof, safeReason(reason), verifiedVertexChanges);
    }

    public ArtistProgress needsCorrection(String reason) {
        requireState(State.OBSERVED_RESULT);
        return copy(State.NEEDS_CORRECTION, proof, safeReason(reason), verifiedVertexChanges);
    }

    public ArtistProgress failed(String reason) {
        if (state == State.DONE) throw new IllegalStateException("COMPLETED_RECEIPT_IMMUTABLE");
        return copy(State.FAILED, proof, safeReason(reason), verifiedVertexChanges);
    }

    /** Semantic bpy actions may show a badge, but never fabricate a touch marker. */
    public boolean displayFingerMarker() { return false; }

    public String badgeText() {
        return state + " • Blender • " + target + " • " + explanation;
    }

    private static String safeReason(String reason) {
        if (reason == null || reason.isEmpty() || reason.length() > 160 ||
            reason.contains("\n") || reason.contains("\r"))
            throw new IllegalArgumentException("INVALID_REASON");
        return reason;
    }

    private void requireState(State expected) {
        if (state != expected) throw new IllegalStateException("INVALID_ARTIST_TRANSITION");
    }

    private ArtistProgress copy(State next, String p, String desc, int vertices) {
        return new ArtistProgress(jobId, operation, target, next,
                                  Objects.requireNonNull(p), expectedPostcondition, Objects.requireNonNull(desc), vertices);
    }
}
