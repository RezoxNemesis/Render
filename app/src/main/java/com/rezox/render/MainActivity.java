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
import com.rezox.render.ui.StudioUi;
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
    private native String nativeDnaCatalog(String absolutePath);
    private native String nativeGpuReport();

    private TextView status;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout page=StudioUi.page(this);
        LinearLayout nav=StudioUi.row(this);
        TextView back=StudioUi.action(this,"←",StudioUi.SECONDARY);
        nav.addView(back,new LinearLayout.LayoutParams(StudioUi.dp(this,52),StudioUi.dp(this,50)));
        back.setOnClickListener(v->finish());
        LinearLayout heading=StudioUi.column(this);
        heading.setPadding(StudioUi.dp(this,13),0,0,0);
        StudioUi.add(heading,StudioUi.label(this,"RENDER  /  LOCAL FILES"));
        StudioUi.add(heading,StudioUi.text(this,"Project Inspector",18,StudioUi.WHITE,true));
        nav.addView(heading,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        StudioUi.add(page,nav);
        StudioUi.space(page,30);
        StudioUi.add(page,StudioUi.text(this,"Every project.\nEvery detail.",30,StudioUi.WHITE,true));
        StudioUi.space(page,10);
        StudioUi.add(page,StudioUi.text(this,
            "Bring your existing .blend projects into Render and inspect their actual stored Blender data without uploading them to a server.",
            14,StudioUi.MUTED,false));
        StudioUi.space(page,20);

        LinearLayout files=StudioUi.card(this);
        StudioUi.add(files,StudioUi.label(this,"01   /   IMPORT"));
        StudioUi.space(files,10);
        StudioUi.add(files,StudioUi.text(this,"Local project library",22,StudioUi.WHITE,true));
        StudioUi.space(files,7);
        StudioUi.add(files,StudioUi.text(this,
            "Use Android Files or a supported Drive document provider. Selected project bytes are copied into Render's app-owned Projects directory.",
            13,StudioUi.MUTED,false));
        StudioUi.space(files,16);
        TextView importer=StudioUi.action(this,"IMPORT .BLEND PROJECT     +",StudioUi.PRIMARY);
        StudioUi.add(files,importer);
        importer.setOnClickListener(v->selectBlend());
        StudioUi.add(page,files);
        StudioUi.space(page,15);

        LinearLayout diagnostics=StudioUi.card(this);
        StudioUi.add(diagnostics,StudioUi.label(this,"02   /   DIAGNOSTICS"));
        StudioUi.space(diagnostics,11);
        TextView core=StudioUi.action(this,"INSPECT NATIVE CORE",StudioUi.SECONDARY);
        StudioUi.add(diagnostics,core);
        core.setOnClickListener(v->status.setText(
            nativeBlenderCoreReady()?"Core integrated: verify actual scene operations":
                nativeEngineStatus()));
        StudioUi.space(diagnostics,11);
        TextView gpu=StudioUi.action(this,"CHECK DEVICE VULKAN",StudioUi.SECONDARY);
        StudioUi.add(diagnostics,gpu);
        gpu.setOnClickListener(v->status.setText(nativeGpuReport()
            + "\nHardware inventory only; launch Full Blender separately to test the real viewport."));
        StudioUi.add(page,diagnostics);
        StudioUi.space(page,15);

        LinearLayout result=StudioUi.card(this);
        StudioUi.add(result,StudioUi.label(this,"NATIVE OUTPUT"));
        StudioUi.space(result,13);
        status=StudioUi.text(this,nativeEngineStatus(),13,StudioUi.WHITE,false);
        status.setTextIsSelectable(true);
        StudioUi.add(result,status);
        StudioUi.add(page,result);
        StudioUi.space(page,18);
        StudioUi.add(page,StudioUi.text(this,
            "File introspection uses Blender's real low-level file readers. The complete Blender editor is a separate native activity inside the Full APK. Google Drive is optional asset storage, never a render server.",
            12,StudioUi.MUTED,false));
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
                    + "\n" + nativeRealBlenderHeader(destination.getAbsolutePath())
                    + "\n" + nativeDnaCatalog(destination.getAbsolutePath()));
        } finally {
            if (!completed) pending.delete();
        }
    }
}
