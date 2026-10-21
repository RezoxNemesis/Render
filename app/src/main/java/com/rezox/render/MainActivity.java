package com.rezox.render;

import android.app.Activity;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;

/**
 * Native Android foundation only. It can safely import local .blend documents.
 * It does not claim to open, evaluate, edit, or render Blender scenes yet.
 */
public final class MainActivity extends Activity {
    private static final int REQUEST_BLEND_FILE = 1201;
    static {
        System.loadLibrary("render_bridge");
    }
    private native String nativeEngineStatus();
    private native boolean nativeBlenderCoreReady();
    private native String nativeInspectBlend(String absolutePath);
    private native String nativeRealBlenderHeader(String absolutePath);
    private native String nativeGpuReport();

    private TextView status;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scrolling = new ScrollView(this);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(28, 34, 28, 34);
        scrolling.addView(content);
        setContentView(scrolling);

        label(content, "Render — Native Blender for Android", 25);
        label(content, "ON-DEVICE ONLY • No streaming or remote workstation", 15);
        label(content, "The Blender engine port is not integrated yet. Importing a .blend file stores it locally but does not open it in an editor.", 15);
        status = label(content, nativeEngineStatus(), 14);

        Button select = new Button(this);
        select.setText("Import local or Drive .blend file");
        content.addView(select, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        select.setOnClickListener(v -> selectBlend());

        Button diagnose = new Button(this);
        diagnose.setText("Check on-device core status");
        content.addView(diagnose);
        diagnose.setOnClickListener(v -> status.setText(
            nativeBlenderCoreReady() ? "Core integrated — check parity tests" : nativeEngineStatus()));

        Button gpu = new Button(this);
        gpu.setText("Inspect on-device Vulkan hardware");
        content.addView(gpu);
        gpu.setOnClickListener(v -> status.setText(nativeGpuReport()
            + "\nThis is device capability detection, not a working 3D renderer."));

        label(content, "Working files: Android app-specific local storage / Projects", 14);
        label(content, "Google Drive / Render / AssetLibrary is an optional library and backup location; it is NOT RAM, GPU, or a render server.", 14);
        label(content, "Milestone: local import, read-only native .blend structure inspection, and Vulkan capability report. Blender scene loading, tools, viewport, simulation and rendering are NOT integrated.", 14);
    }

    private TextView label(LinearLayout parent, String value, int size) {
        TextView label = new TextView(this);
        label.setText(value);
        label.setTextSize(size);
        label.setPadding(0, 8, 0, 12);
        parent.addView(label);
        return label;
    }

    private void selectBlend() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*"); // .blend is not consistently associated with a MIME type.
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivityForResult(intent, REQUEST_BLEND_FILE);
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != REQUEST_BLEND_FILE || result != RESULT_OK || data == null || data.getData() == null) return;
        Uri source = data.getData();
        status.setText("Copying .blend file into local app storage...");
        new Thread(() -> {
            try {
                String resultText = importBlend(source);
                runOnUiThread(() -> status.setText(resultText));
            } catch (Exception e) {
                runOnUiThread(() -> status.setText("Import failed: " + e.getClass().getSimpleName()
                    + (e.getMessage() == null ? "" : " — " + e.getMessage())));
            }
        }, "blend-import").start();
    }

    private String displayName(Uri uri) {
        try (Cursor cursor = getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int col = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (col >= 0 && !cursor.isNull(col)) return cursor.getString(col);
            }
        } catch (RuntimeException ignored) {
            // A SAF provider may not expose a display name.
        }
        return "import.blend";
    }

    private String importBlend(Uri source) throws IOException, NoSuchAlgorithmException {
        File storage = getExternalFilesDir(null);
        if (storage == null) storage = getFilesDir();
        File projects = new File(storage, "Projects");
        if (!projects.isDirectory() && !projects.mkdirs()) throw new IOException("Cannot create Projects directory");

        String name = SafeNames.blendFileName(displayName(source));
        File pending = File.createTempFile("render-import-", ".part", projects);
        boolean completed = false;
        try {
            MessageDigest sha = MessageDigest.getInstance("SHA-256");
            long total = 0;
            try (InputStream opened = getContentResolver().openInputStream(source)) {
                if (opened == null) throw new IOException("Provider returned no data");
                try (InputStream in = new BufferedInputStream(opened);
                     OutputStream out = new BufferedOutputStream(Files.newOutputStream(pending.toPath()))) {
                    byte[] header = new byte[7];
                    int offset = 0;
                    while (offset < header.length) {
                        int count = in.read(header, offset, header.length - offset);
                        if (count < 0) throw new IOException("Not a valid Blender .blend header");
                        if (count == 0) continue;
                        offset += count;
                    }
                    boolean rawBlend = "BLENDER".equals(new String(header, StandardCharsets.US_ASCII));
                    boolean gzipCandidate = (header[0] & 0xff) == 0x1f && (header[1] & 0xff) == 0x8b;
                    boolean zstdCandidate = (header[0] & 0xff) == 0x28 && (header[1] & 0xff) == 0xb5
                        && (header[2] & 0xff) == 0x2f && (header[3] & 0xff) == 0xfd;
                    if (!rawBlend && !gzipCandidate && !zstdCandidate)
                        throw new IOException("Unrecognized Blender file signature (raw, gzip or zstd)");
                    // Compressed .blend is a candidate only; native preflight does not decompress
                    // or claim that a compressed file is a valid Blender scene.
                    out.write(header);
                    sha.update(header);
                    total += header.length;
                    byte[] buffer = new byte[1024 * 1024];
                    int count;
                    while ((count = in.read(buffer)) != -1) {
                        if (count == 0) continue;
                        out.write(buffer, 0, count);
                        sha.update(buffer, 0, count);
                        total += count;
                    }
                }
            }
            String prefix = Long.toHexString(System.currentTimeMillis()) + "-";
            File destination = new File(projects, prefix + name);
            try {
                Files.move(pending.toPath(), destination.toPath(), StandardCopyOption.ATOMIC_MOVE);
            } catch (IOException cannotBeAtomic) {
                Files.move(pending.toPath(), destination.toPath());
            }
            completed = true;
            byte[] digest = sha.digest();
            StringBuilder hex = new StringBuilder();
            for (byte b : digest) hex.append(String.format(Locale.ROOT, "%02x", b & 0xff));
            return String.format(Locale.ROOT,
                "Imported %s (%d bytes) locally. SHA-256: %s.\nLow-level format preflight: %s\nBlender scene editing and rendering remain unavailable.",
                name, total, hex, nativeInspectBlend(destination.getAbsolutePath())
                    + "\n" + nativeRealBlenderHeader(destination.getAbsolutePath()));
        } finally {
            if (!completed) pending.delete();
        }
    }
}
