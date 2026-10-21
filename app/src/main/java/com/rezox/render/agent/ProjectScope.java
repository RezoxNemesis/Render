package com.rezox.render.agent;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Only direct, regular .blend files in Render's own Projects folders are visible. */
public final class ProjectScope {
    private final File[] roots;
    public ProjectScope(File[] roots) throws IOException {
        this.roots = new File[roots.length];
        for (int i=0; i<roots.length; i++) this.roots[i] = roots[i].getCanonicalFile();
    }
    public String id(int root, String name) { return AgentPolicy.sha256(root + ":" + name); }
    public static final class Entry {
        public final String id;
        public final File file;
        Entry(String id, File file) { this.id=id; this.file=file; }
    }
    public List<Entry> entries() throws IOException {
        List<Entry> out = new ArrayList<>();
        for (int i=0; i<roots.length; i++) {
            File[] files = roots[i].listFiles();
            if (files == null) continue;
            for (File f : files) {
                if (!f.getName().toLowerCase(java.util.Locale.ROOT).endsWith(".blend")
                        || Files.isSymbolicLink(f.toPath()) || !f.isFile()) continue;
                File canonical = f.getCanonicalFile();
                if (!roots[i].equals(canonical.getParentFile())) continue;
                out.add(new Entry(id(i,f.getName()), canonical));
            }
        }
        out.sort(Comparator.comparing(e -> e.id));
        return out;
    }
    public File find(String id) throws IOException {
        if (id == null || !id.matches("[a-f0-9]{64}")) throw new IllegalArgumentException("INVALID_PROJECT_ID");
        for (Entry entry : entries()) if (entry.id.equals(id)) return entry.file;
        throw new IllegalArgumentException("PROJECT_NOT_FOUND");
    }
}
