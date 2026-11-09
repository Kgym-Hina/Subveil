package io.github.kgymhina.subveil;

import android.os.SystemClock;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** Holds the loaded cues and extrapolates the player position between syncs. */
final class SubtitleEngine {
    private List<Cue> cues = new ArrayList<>();
    private String name = "";
    private long offsetMs;
    private long anchorPosMs;
    private long anchorClockMs;
    private boolean playing;
    private boolean visible = true;
    private boolean idle;

    synchronized void load(String n, List<Cue> c) {
        name = n;
        cues = c;
    }

    synchronized String name() {
        return name;
    }

    synchronized long offsetMs() {
        return offsetMs;
    }

    synchronized void clear() {
        name = "";
        cues = new ArrayList<>();
    }

    synchronized void sync(long posMs, boolean isPlaying) {
        anchorPosMs = posMs;
        anchorClockMs = SystemClock.elapsedRealtime();
        playing = isPlaying;
    }

    /** Starts or pauses the clock without moving the current position. */
    synchronized void setPlaying(boolean isPlaying) {
        sync(positionMs(), isPlaying);
    }

    synchronized void seekTo(long posMs) {
        sync(Math.max(0, posMs), playing);
    }

    synchronized void seekBy(long deltaMs) {
        seekTo(positionMs() + deltaMs);
    }

    synchronized boolean isPlaying() {
        return playing;
    }

    synchronized void setOffset(long ms) {
        offsetMs = ms;
    }

    synchronized void setVisible(boolean v) {
        visible = v;
    }

    /** True while the source has nothing playing; the clock is stopped and no text is shown. */
    synchronized void setIdle(boolean v) {
        if (v && !idle) sync(positionMs(), false);
        idle = v;
    }

    synchronized long positionMs() {
        return anchorPosMs + (playing ? SystemClock.elapsedRealtime() - anchorClockMs : 0);
    }

    /** Positive offsets show subtitles later. */
    synchronized String currentText() {
        if (!visible || idle || cues.isEmpty()) return "";
        long t = positionMs() - offsetMs;
        StringBuilder sb = new StringBuilder();
        for (Cue c : cues) {
            if (c.startMs > t) break;
            if (t < c.endMs) {
                if (sb.length() > 0) sb.append('\n');
                sb.append(c.text);
            }
        }
        return sb.toString();
    }

    synchronized JSONObject status() throws JSONException {
        JSONObject o = new JSONObject();
        o.put("name", name);
        o.put("cues", cues.size());
        o.put("offset_ms", offsetMs);
        o.put("position_ms", positionMs());
        o.put("playing", playing);
        o.put("visible", visible);
        o.put("text", currentText());
        return o;
    }
}
