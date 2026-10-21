package com.rezox.render;

import java.util.Locale;

/** Maps untrusted Storage Access Framework display names into one local filename. */
public final class SafeNames {
    private SafeNames() {}

    public static String blendFileName(String untrusted) {
        String cleaned = untrusted == null ? "" : untrusted.trim();
        cleaned = cleaned.replaceAll("[^A-Za-z0-9._-]", "_").replaceAll("^\\.+", "");
        if (cleaned.isEmpty()) cleaned = "untitled";
        if (!cleaned.toLowerCase(Locale.ROOT).endsWith(".blend")) cleaned += ".blend";
        if (cleaned.length() > 96) cleaned = cleaned.substring(0, 90) + ".blend";
        return cleaned;
    }
}
