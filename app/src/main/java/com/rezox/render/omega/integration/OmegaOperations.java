package com.rezox.render.omega.integration;

import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.Set;

/** Frozen RENDER-OMEGA-1 transport allowlist, not a claim that a phase is installed. */
public final class OmegaOperations {
    private OmegaOperations() {}
    private static final Set<String> RESERVED = Collections.unmodifiableSet(new LinkedHashSet<>(
        Arrays.asList(
            "omega.engine.diagnose", "omega.engine.viewport_profile",
            "omega.render.preflight", "omega.render.job_status",
            "omega.agent.plan_validate", "omega.agent.journal_status",
            "omega.geometry.bridge_loops", "omega.geometry.inspect",
            "omega.character.create", "omega.character.audit",
            "omega.rig.bind", "omega.rig.audit",
            "omega.motion.create_actions", "omega.motion.audit",
            "omega.world.build_scene", "omega.world.audit",
            "omega.vfx.create_grade", "omega.vfx.cache_inspect",
            "omega.integration.capabilities", "omega.integration.audit",
            "omega.artist.inspect_ui", "omega.artist.execute_tool",
            "omega.quality.inspect", "omega.quality.revise_plan",
            "omega.simulation.bake", "omega.simulation.inspect_cache"
        )));

    public static boolean isReserved(String name) { return RESERVED.contains(name); }
    public static Set<String> reserved() { return RESERVED; }
}
