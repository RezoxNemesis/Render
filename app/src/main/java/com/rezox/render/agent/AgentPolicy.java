package com.rezox.render.agent;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Map;
import java.util.LinkedHashMap;
import java.util.HashSet;
import java.util.Arrays;
import java.util.Collections;
import java.util.Set;

/** Pure validation shared by the Android agent and host regression tests. */
public final class AgentPolicy {
    private AgentPolicy() {}
    public static final Map<String, Set<String>> ACTIONS;
    static {
        Map<String, Set<String>> registry = new LinkedHashMap<>();
        registry.put("engine.status", Collections.emptySet());
        registry.put("projects.list", fields("offset", "limit"));
        registry.put("projects.inspect", fields("project_id", "expected_sha256"));
        registry.put("gpu.info", Collections.emptySet());
        registry.put("blender.scene.summary", Collections.emptySet());
        registry.put("blender.object.add_cube", fields("name", "size", "location"));
        registry.put("blender.scene.set_frame", fields("frame"));
        registry.put("blender.object.set_transform", fields("name", "location", "rotation_euler", "scale"));
        registry.put("blender.object.keyframe", fields("name", "frame", "data_path", "value"));
        registry.put("blender.project.save_copy", Collections.emptySet());
        ACTIONS = Collections.unmodifiableMap(registry);
    }
    private static Set<String> fields(String... values) {
        return Collections.unmodifiableSet(new HashSet<>(Arrays.asList(values)));
    }

    public static String relayUrl(String value) {
        try {
            URI u = new URI(value.trim());
            if (!"https".equals(u.getScheme()) || u.getHost() == null || u.getUserInfo() != null
                    || u.getQuery() != null || u.getFragment() != null || u.getPort() > 65535 || u.getPort() == 0
                    || (!u.getPath().isEmpty() && !u.getPath().equals("/")))
                throw new IllegalArgumentException("Use the relay HTTPS origin, without a path or credentials");
            return value.trim().replaceAll("/+$", "");
        } catch (java.net.URISyntaxException e) {
            throw new IllegalArgumentException("Invalid relay address");
        }
    }
    public static void validate(String request, int version, String action, Set<String> fields) {
        if (request == null || !request.matches("[A-Za-z0-9._-]{1,128}"))
            throw new IllegalArgumentException("INVALID_REQUEST_ID");
        if (version != 1) throw new IllegalArgumentException("UNSUPPORTED_PROTOCOL_VERSION");
        if (!ACTIONS.containsKey(action)) throw new IllegalArgumentException("NATIVE_ACTION_UNAVAILABLE");
        if (!ACTIONS.get(action).containsAll(fields)) throw new IllegalArgumentException("UNKNOWN_ARGUMENT");
        if (action.equals("projects.inspect") && !fields.contains("project_id"))
            throw new IllegalArgumentException("PROJECT_ID_REQUIRED");
        if (action.equals("blender.scene.set_frame") && !fields.contains("frame"))
            throw new IllegalArgumentException("FRAME_REQUIRED");
        if ((action.equals("blender.object.set_transform") || action.equals("blender.object.keyframe"))
            && !fields.contains("name")) throw new IllegalArgumentException("OBJECT_NAME_REQUIRED");
        if (action.equals("blender.object.set_transform")
            && !fields.contains("location") && !fields.contains("rotation_euler") && !fields.contains("scale"))
            throw new IllegalArgumentException("TRANSFORM_FIELD_REQUIRED");
        if (action.equals("blender.object.keyframe")
            && !(fields.contains("data_path") && fields.contains("frame") && fields.contains("value")))
            throw new IllegalArgumentException("KEYFRAME_FIELDS_REQUIRED");
    }
    public static String sha256(String value) {
        try { return hex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))); }
        catch (java.security.NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }
    public static String hex(byte[] bytes) {
        StringBuilder out = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) out.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
        return out.toString();
    }
}
