package com.rezox.render.omega.artist;

import org.junit.Test;
import static org.junit.Assert.*;

public final class ArtistProgressTest {
    private static final String JOB="1234567890abcdef1234567890abcdef";
    private static final String OLD="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    private static final String NEW="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    private static ArtistProgress queued() {
        return ArtistProgress.queued(JOB,"omega.artist.execute_tool","OmegaMesh","evaluated_mesh_changed");
    }

    @Test public void validatedNativeEvidenceRequiredToClaimDone() {
        ArtistProgress initial=queued();
        assertEquals(ArtistProgress.State.QUEUED, initial.state);
        try { initial.done(); fail(); } catch(IllegalStateException expected) {}
        ArtistProgress started=initial.executing("OmegaMesh");
        assertEquals(ArtistProgress.State.EXECUTING, started.state);
        try { started.done(); fail(); } catch(IllegalStateException expected) {}
        ArtistProgress verified=started.observed("OmegaMesh","evaluated_mesh_changed",OLD,NEW,7,true);
        assertEquals(ArtistProgress.State.OBSERVED_RESULT, verified.state);
        assertEquals(7,verified.verifiedVertexChanges);
        assertEquals(ArtistProgress.State.DONE,verified.done().state);
        assertFalse(verified.displayFingerMarker());
        assertEquals("evaluated_mesh_changed", verified.expectedPostcondition);
        assertTrue(verified.badgeText().contains("OmegaMesh"));
    }

    @Test public void noFakeReceiptAccepted() {
        ArtistProgress started=queued().executing("OmegaMesh");
        for(boolean verified:new boolean[]{false}){
            try { started.observed("OmegaMesh","evaluated_mesh_changed",OLD,NEW,4,verified); fail(); }
            catch(IllegalArgumentException expected) {}
        }
        try { started.observed("OmegaMesh","evaluated_mesh_changed",OLD,OLD,4,true); fail(); }
        catch(IllegalArgumentException expected) {}
        try { started.observed("OmegaMesh","evaluated_mesh_changed",OLD,NEW,0,true); fail(); }
        catch(IllegalArgumentException expected) {}
        try { started.observed("Other","evaluated_mesh_changed",OLD,NEW,4,true); fail(); }
        catch(IllegalArgumentException expected) {}
        try { started.observed("OmegaMesh","opaque_claim",OLD,NEW,4,true); fail(); }
        catch(IllegalArgumentException expected) {}
    }

    @Test public void boundariesAndStageTransitions() {
        try { ArtistProgress.queued("../../", "omega.artist.execute_tool", "OmegaMesh","selection_active"); fail(); }
        catch(IllegalArgumentException expected) {}
        try { ArtistProgress.queued(JOB, "shell.exec", "OmegaMesh","selection_active"); fail(); }
        catch(IllegalArgumentException expected) {}
        try { ArtistProgress.queued(JOB, "omega.artist.execute_tool", "../Gallery","selection_active"); fail(); }
        catch(IllegalArgumentException expected) {}
        ArtistProgress queued=queued();
        ArtistProgress inspect=ArtistProgress.queued(JOB,"omega.artist.inspect_ui","OmegaMesh","inspected_native_scene");
        assertEquals(ArtistProgress.State.DONE,inspect.executing("OmegaMesh").observed("OmegaMesh","inspected_native_scene",OLD,OLD,0,true).done().state);
        try { queued.executing("OtherMesh"); fail(); }
        catch(IllegalArgumentException expected) {}
        ArtistProgress paused=queued.paused("Awaiting foreground native editor");
        assertEquals(ArtistProgress.State.PAUSED,paused.state);
        assertEquals(ArtistProgress.State.FAILED,paused.failed("Cancelled").state);
        ArtistProgress started=ArtistProgress.queued(JOB,"omega.artist.execute_tool","OmegaMesh","mode_changed").executing("OmegaMesh");
        ArtistProgress observed=started.observed("OmegaMesh","mode_changed",OLD,NEW,0,true);
        assertEquals(ArtistProgress.State.NEEDS_CORRECTION,observed.needsCorrection("Native mode incorrect").state);
        try { observed.done().failed("late update"); fail(); }
        catch(IllegalStateException expected) {}
    }
}
