package io.github.kgymhina.subveil;

import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Parses SRT, WebVTT and ASS/SSA subtitles. */
final class SubtitleParser {
    private static final Pattern TIMING = Pattern.compile(
            "((?:\\d+:)?\\d{1,2}:\\d{1,2}[,.]\\d{1,3})\\s*-->\\s*((?:\\d+:)?\\d{1,2}:\\d{1,2}[,.]\\d{1,3})");

    private SubtitleParser() {}

    static String decode(byte[] b) {
        if (b.length >= 3 && (b[0] & 0xff) == 0xEF && (b[1] & 0xff) == 0xBB && (b[2] & 0xff) == 0xBF) {
            return new String(b, 3, b.length - 3, StandardCharsets.UTF_8);
        }
        if (b.length >= 2 && (b[0] & 0xff) == 0xFF && (b[1] & 0xff) == 0xFE) {
            return new String(b, 2, b.length - 2, StandardCharsets.UTF_16LE);
        }
        if (b.length >= 2 && (b[0] & 0xff) == 0xFE && (b[1] & 0xff) == 0xFF) {
            return new String(b, 2, b.length - 2, StandardCharsets.UTF_16BE);
        }
        try {
            return StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(b)).toString();
        } catch (CharacterCodingException e) {
            // Chinese subtitles without a BOM are usually GBK.
            return new String(b, Charset.forName("GB18030"));
        }
    }

    static List<Cue> parse(String text) {
        text = text.replace("\r\n", "\n").replace('\r', '\n');
        List<Cue> cues = text.contains("[Events]") ? parseAss(text) : parseTimed(text);
        Collections.sort(cues, (a, b) -> Long.compare(a.startMs, b.startMs));
        return cues;
    }

    private static List<Cue> parseTimed(String text) {
        List<Cue> cues = new ArrayList<>();
        String[] lines = text.split("\n");
        for (int i = 0; i < lines.length; i++) {
            Matcher m = TIMING.matcher(lines[i]);
            if (!m.find()) continue;
            long start = parseTime(m.group(1));
            long end = parseTime(m.group(2));
            StringBuilder sb = new StringBuilder();
            while (i + 1 < lines.length && !lines[i + 1].trim().isEmpty()) {
                i++;
                if (sb.length() > 0) sb.append('\n');
                sb.append(lines[i].trim());
            }
            String t = clean(sb.toString());
            if (!t.isEmpty()) cues.add(new Cue(start, end, t));
        }
        return cues;
    }

    private static List<Cue> parseAss(String text) {
        List<Cue> cues = new ArrayList<>();
        int startIdx = 1, endIdx = 2, textIdx = 9, fields = 10;
        boolean inEvents = false;
        for (String raw : text.split("\n")) {
            String line = raw.trim();
            if (line.startsWith("[")) {
                inEvents = line.equalsIgnoreCase("[Events]");
                continue;
            }
            if (!inEvents) continue;
            if (line.startsWith("Format:")) {
                String[] names = line.substring(7).split(",");
                fields = names.length;
                for (int i = 0; i < names.length; i++) {
                    String n = names[i].trim();
                    if (n.equalsIgnoreCase("Start")) startIdx = i;
                    else if (n.equalsIgnoreCase("End")) endIdx = i;
                    else if (n.equalsIgnoreCase("Text")) textIdx = i;
                }
            } else if (line.startsWith("Dialogue:")) {
                String[] v = line.substring(9).split(",", fields);
                if (v.length < fields) continue;
                String t = v[textIdx].replace("\\N", "\n").replace("\\n", "\n").replace("\\h", " ");
                t = clean(t);
                if (!t.isEmpty()) cues.add(new Cue(parseTime(v[startIdx]), parseTime(v[endIdx]), t));
            }
        }
        return cues;
    }

    private static String clean(String t) {
        return t.replaceAll("\\{[^}]*\\}", "").replaceAll("<[^>]*>", "").trim();
    }

    static long parseTime(String s) {
        s = s.trim().replace(',', '.');
        String[] p = s.split(":");
        String last = p[p.length - 1];
        int dot = last.indexOf('.');
        long sec = Long.parseLong(dot < 0 ? last : last.substring(0, dot));
        long ms = 0;
        if (dot >= 0) {
            String frac = (last.substring(dot + 1) + "000").substring(0, 3);
            ms = Long.parseLong(frac);
        }
        long min = p.length >= 2 ? Long.parseLong(p[p.length - 2].trim()) : 0;
        long hour = p.length >= 3 ? Long.parseLong(p[p.length - 3].trim()) : 0;
        return ((hour * 60 + min) * 60 + sec) * 1000 + ms;
    }
}
