package io.github.kgymhina.subveil;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.List;

/**
 * Follows what a paired Apple TV is playing: keeps the subtitle clock in step with it and
 * fetches subtitles from OpenSubtitles when the title changes.
 */
final class AppleTvSync {
    private static final String TAG = "Subveil";
    private static final long POLL_MS = 1000;
    private static final long MAX_DRIFT_MS = 1500;

    interface Subtitles {
        String apiKey() throws Exception;

        List<String> languages();

        void loaded(String name, List<Cue> cues);
    }

    private final AppleTv atv;
    private final SharedPreferences prefs;
    private final SubtitleEngine engine;
    private final Subtitles subtitles;
    private volatile boolean running;
    private volatile String lastKey = "";
    private volatile String autoMessage = "";
    private volatile JSONObject lastStatus = new JSONObject();
    private Thread thread;

    AppleTvSync(Context context, SharedPreferences prefs, SubtitleEngine engine, Subtitles subtitles) {
        this.atv = new AppleTv(context);
        this.prefs = prefs;
        this.engine = engine;
        this.subtitles = subtitles;
    }

    void start() {
        if (!AppleTv.supported()) return;
        running = true;
        thread = new Thread(this::loop, "apple-tv");
        thread.start();
    }

    void stop() {
        running = false;
        if (thread != null) thread.interrupt();
    }

    private void loop() {
        try {
            String creds = prefs.getString("atv_creds", "");
            if (!creds.isEmpty()) {
                atv.connect(prefs.getString("atv_id", ""), prefs.getString("atv_address", ""), creds);
            }
        } catch (Exception e) {
            Log.w(TAG, "Apple TV connect failed", e);
        }
        while (running) {
            try {
                poll();
                Thread.sleep(POLL_MS);
            } catch (InterruptedException e) {
                return;
            } catch (Exception e) {
                Log.w(TAG, "Apple TV poll failed", e);
                try {
                    Thread.sleep(5000);
                } catch (InterruptedException ie) {
                    return;
                }
            }
        }
    }

    private void poll() throws Exception {
        JSONObject s = new JSONObject(atv.status());
        lastStatus = s;
        JSONObject p = s.optJSONObject("playing");
        if (p == null) return;
        String state = p.optString("state");
        if (prefs.getBoolean("atv_auto_sync", true) && p.has("position_ms")) {
            boolean playing = state.equals("playing");
            long pos = p.getLong("position_ms");
            if (playing != engine.isPlaying() || Math.abs(engine.positionMs() - pos) > MAX_DRIFT_MS) {
                engine.sync(pos, playing);
            }
        }
        String title = p.optString("title");
        String series = p.optString("series");
        if (title.isEmpty() && series.isEmpty()) return;
        String key = series + "|" + title + "|" + p.opt("season") + "|" + p.opt("episode");
        if (!key.equals(lastKey)) {
            lastKey = key;
            if (prefs.getBoolean("atv_auto_search", true)) autoSearch(p);
        }
    }

    private void autoSearch(JSONObject p) {
        String series = p.optString("series");
        String query = series.isEmpty() ? p.optString("title") : series;
        Integer season = p.isNull("season") ? null : p.optInt("season");
        Integer episode = p.isNull("episode") ? null : p.optInt("episode");
        try {
            String key = subtitles.apiKey();
            JSONArray results = OpenSubtitles.search(key, query, subtitles.languages(), season, episode);
            if (results.length() == 0) {
                autoMessage = "no subtitles found for " + query;
                return;
            }
            OpenSubtitles.Download d = OpenSubtitles.download(key, results.getJSONObject(0).getLong("file_id"));
            List<Cue> cues = SubtitleParser.parse(SubtitleParser.decode(d.data));
            if (cues.isEmpty()) {
                autoMessage = "no cues in " + d.name;
                return;
            }
            subtitles.loaded(d.name, cues);
            autoMessage = "loaded " + d.name + " for " + query;
        } catch (Exception e) {
            autoMessage = "search for " + query + " failed: " + e.getMessage();
        }
        Log.i(TAG, "auto search: " + autoMessage);
    }

    JSONObject status() throws Exception {
        return new JSONObject()
                .put("ok", true)
                .put("supported", AppleTv.supported())
                .put("paired", !prefs.getString("atv_creds", "").isEmpty())
                .put("name", prefs.getString("atv_name", ""))
                .put("auto_search", prefs.getBoolean("atv_auto_search", true))
                .put("auto_sync", prefs.getBoolean("atv_auto_sync", true))
                .put("auto_message", autoMessage)
                .put("connection", lastStatus);
    }

    JSONArray scan() throws Exception {
        return new JSONArray(atv.scan());
    }

    JSONObject pairBegin(String id, String address, String name) throws Exception {
        prefs.edit().putString("atv_pending_id", id).putString("atv_pending_address", address)
                .putString("atv_pending_name", name).apply();
        return new JSONObject(atv.pairBegin(id, address));
    }

    void pairFinish(String pin) throws Exception {
        String creds = new JSONObject(atv.pairFinish(pin)).getString("credentials");
        String id = prefs.getString("atv_pending_id", "");
        String address = prefs.getString("atv_pending_address", "");
        prefs.edit().putString("atv_id", id).putString("atv_address", address)
                .putString("atv_name", prefs.getString("atv_pending_name", ""))
                .putString("atv_creds", creds).apply();
        lastKey = "";
        atv.connect(id, address, creds);
    }

    void forget() throws Exception {
        atv.disconnect();
        prefs.edit().remove("atv_id").remove("atv_address").remove("atv_name").remove("atv_creds").apply();
        lastStatus = new JSONObject();
    }

    void setOptions(JSONObject o) {
        SharedPreferences.Editor e = prefs.edit();
        if (o.has("auto_search")) e.putBoolean("atv_auto_search", o.optBoolean("auto_search"));
        if (o.has("auto_sync")) e.putBoolean("atv_auto_sync", o.optBoolean("auto_sync"));
        e.apply();
    }
}
