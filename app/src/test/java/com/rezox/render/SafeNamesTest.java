package com.rezox.render;

import org.junit.Test;
import static org.junit.Assert.*;

public class SafeNamesTest {
    @Test public void blocksTraversalAndSlash() {
        String name = SafeNames.blendFileName("../../../../other\\folder/scene.blend");
        assertFalse(name.startsWith("."));
        assertFalse(name.contains("/"));
        assertFalse(name.contains("\\"));
        assertTrue(name.endsWith(".blend"));
    }

    @Test public void preservesAndAddsExtension() {
        assertEquals("scene.blend", SafeNames.blendFileName("scene.blend"));
        assertEquals("scene.blend", SafeNames.blendFileName("scene"));
        assertEquals("untitled.blend", SafeNames.blendFileName(null));
    }

    @Test public void boundsFileNames() {
        assertTrue(SafeNames.blendFileName("x".repeat(1000)).length() <= 96);
    }
}
