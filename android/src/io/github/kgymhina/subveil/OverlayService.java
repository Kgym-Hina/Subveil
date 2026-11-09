package io.github.kgymhina.subveil;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.Settings;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public class OverlayService extends Service {
    static final String TAG = "Subveil";
    static final int PORT = 8765;
    static final String ACTION_DETACH = "io.github.kgymhina.subveil.DETACH";
    static final String ACTION_ATTACH = "io.github.kgymhina.subveil.ATTACH";
    private static final String CHANNEL = "overlay";
    private static final long ATTACH_DELAY_MS = 3000;
    private WindowManager.LayoutParams layoutParams;
    private final Runnable attach = this::attachOverlay;
    private static final float DEFAULT_TEXT_PX = 40f;

    private final Handler main = new Handler(Looper.getMainLooper());
    private final SubtitleEngine engine = new SubtitleEngine();
    private WindowManager wm;
    private TextView view;
    private HttpServer server;
    private SharedPreferences prefs;
    private String lastText = null;
    private volatile String notice = "";
    private volatile long noticeUntil = 0;

    private final Runnable tick = new Runnable() {
        @Override
        public void run() {
            String t = SystemClock.elapsedRealtime() < noticeUntil ? notice : engine.currentText();
            if (view != null && !t.equals(lastText)) {
                lastText = t;
                view.setText(t);
                view.setVisibility(t.isEmpty() ? View.INVISIBLE : View.VISIBLE);
            }
            main.postDelayed(this, 50);
        }
    };

    @Override
    public void onCreate() {
        super.onCreate();
        prefs = getSharedPreferences("settings", MODE_PRIVATE);
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel(CHANNEL, getString(R.string.channel_name), NotificationManager.IMPORTANCE_LOW));
        Notification n = new Notification.Builder(this, CHANNEL)
                .setContentTitle(getString(R.string.service_running))
                .setSmallIcon(R.drawable.ic_notification)
                .build();
        startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);

        addOverlay();
        server = new HttpServer(PORT, this::handle);
        server.start();
        main.post(tick);
    }

    private void addOverlay() {
        if (!Settings.canDrawOverlays(this)) {
            Log.e(TAG, "SYSTEM_ALERT_WINDOW not granted; overlay disabled");
            return;
        }
        view = new TextView(this);
        view.setTextSize(TypedValue.COMPLEX_UNIT_PX, prefs.getFloat("text_px", DEFAULT_TEXT_PX));
        view.setTextColor(Color.WHITE);
        view.setShadowLayer(6f, 0f, 0f, Color.BLACK);
        view.setBackgroundColor(0x66000000);
        view.setPadding(28, 8, 28, 8);
        view.setGravity(Gravity.CENTER);
        view.setMaxWidth(1600);
        view.setVisibility(View.INVISIBLE);

        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL;
        lp.y = 60;

        wm = getSystemService(WindowManager.class);
        layoutParams = lp;
        attachOverlay();
    }

    private void attachOverlay() {
        if (view == null || view.isAttachedToWindow()) return;
        try {
            wm.addView(view, layoutParams);
            Log.i(TAG, "overlay added");
        } catch (Exception e) {
            Log.e(TAG, "addView failed", e);
        }
    }

    // MitvWindowManager force-stops an app that still owns an overlay window when its
    // activity leaves the foreground, so the overlay is detached while MainActivity is shown.
    private void detachOverlay() {
        main.removeCallbacks(attach);
        if (view != null && view.isAttachedToWindow()) {
            wm.removeViewImmediate(view);
            Log.i(TAG, "overlay detached");
        }
    }

    private HttpServer.Response handle(HttpServer.Request r) throws Exception {
        String route = r.method + " " + r.path;
        switch (route) {
            case "GET /":
            case "GET /index.html":
                return new HttpServer.Response(200, "text/html; charset=utf-8", readAsset("index.html"));
            case "GET /status": {
                JSONObject o = engine.status();
                o.put("ok", true);
                o.put("version", 1);
                o.put("app_version", BuildInfo.VERSION);
                o.put("standalone", BuildInfo.STANDALONE);
                o.put("overlay", view != null);
                o.put("text_size_px", prefs.getFloat("text_px", DEFAULT_TEXT_PX));
                return HttpServer.Response.json(200, o);
            }
            case "POST /subtitle": {
                String name = r.query.containsKey("name") ? r.query.get("name") : "subtitle";
                List<Cue> cues = SubtitleParser.parse(SubtitleParser.decode(r.body));
                if (cues.isEmpty()) return HttpServer.Response.error(400, "no cues found");
                engine.load(name, cues);
                Log.i(TAG, "loaded " + name + " (" + cues.size() + " cues)");
                return HttpServer.Response.json(200, ok().put("cues", cues.size()));
            }
            case "GET /settings":
                return HttpServer.Response.json(200, settingsJson());
            case "POST /settings": {
                JSONObject o = r.json();
                SharedPreferences.Editor e = prefs.edit();
                if (o.has("api_key")) e.putString("os_api_key", o.getString("api_key").trim());
                if (o.has("languages")) e.putString("languages", o.getString("languages").trim());
                e.apply();
                return HttpServer.Response.json(200, settingsJson());
            }
            case "POST /search": {
                JSONObject o = r.json();
                String query = o.optString("query", "").trim();
                if (query.isEmpty()) return HttpServer.Response.error(400, "query is required");
                Integer season = o.has("season") ? o.getInt("season") : null;
                Integer episode = o.has("episode") ? o.getInt("episode") : null;
                JSONArray results = OpenSubtitles.search(apiKey(), query, languages(), season, episode);
                return HttpServer.Response.json(200, ok().put("results", results));
            }
            case "POST /download": {
                OpenSubtitles.Download d = OpenSubtitles.download(apiKey(), r.json().getLong("file_id"));
                List<Cue> cues = SubtitleParser.parse(SubtitleParser.decode(d.data));
                if (cues.isEmpty()) return HttpServer.Response.error(400, "no cues found in " + d.name);
                engine.load(d.name, cues);
                return HttpServer.Response.json(200, ok().put("name", d.name).put("cues", cues.size()));
            }
            case "POST /clock": {
                JSONObject o = r.json();
                switch (o.getString("action")) {
                    case "play": engine.setPlaying(true); break;
                    case "pause": engine.setPlaying(false); break;
                    case "toggle": engine.setPlaying(!engine.isPlaying()); break;
                    case "seek": engine.seekBy(o.getLong("delta_ms")); break;
                    case "set": engine.seekTo(o.getLong("position_ms")); break;
                    default: return HttpServer.Response.error(400, "unknown action");
                }
                return HttpServer.Response.json(200, ok());
            }
            case "POST /clear":
                engine.clear();
                return HttpServer.Response.json(200, ok());
            case "POST /sync": {
                JSONObject o = r.json();
                engine.sync(o.getLong("position_ms"), o.optBoolean("playing", true));
                if (o.has("visible")) engine.setVisible(o.getBoolean("visible"));
                if (o.has("offset_ms")) engine.setOffset(o.getLong("offset_ms"));
                return HttpServer.Response.json(200, ok());
            }
            case "POST /offset": {
                long ms = r.json().getLong("offset_ms");
                engine.setOffset(ms);
                if (r.query.containsKey("notify")) {
                    notice = getString(R.string.offset_notice, ms / 1000.0);
                    noticeUntil = SystemClock.elapsedRealtime() + 2000;
                }
                return HttpServer.Response.json(200, ok());
            }
            case "POST /visible":
                engine.setVisible(r.json().getBoolean("visible"));
                return HttpServer.Response.json(200, ok());
            case "POST /style": {
                float px = (float) r.json().getDouble("text_size_px");
                prefs.edit().putFloat("text_px", px).apply();
                main.post(() -> {
                    if (view != null) view.setTextSize(TypedValue.COMPLEX_UNIT_PX, px);
                });
                return HttpServer.Response.json(200, ok());
            }
            default:
                return HttpServer.Response.error(404, "not found: " + route);
        }
    }

    private String apiKey() throws Exception {
        String key = prefs.getString("os_api_key", "");
        if (key.isEmpty()) throw new IllegalStateException("OpenSubtitles API key is not set");
        return key;
    }

    private List<String> languages() {
        List<String> out = new ArrayList<>();
        for (String l : prefs.getString("languages", "en").split(",")) {
            if (!l.trim().isEmpty()) out.add(l.trim().toLowerCase(Locale.ROOT));
        }
        return out;
    }

    private JSONObject settingsJson() throws Exception {
        String key = prefs.getString("os_api_key", "");
        return ok()
                .put("api_key_set", !key.isEmpty())
                .put("api_key_hint", key.length() > 4 ? "…" + key.substring(key.length() - 4) : "")
                .put("languages", prefs.getString("languages", "en"));
    }

    private static JSONObject ok() throws Exception {
        return new JSONObject().put("ok", true);
    }

    private byte[] readAsset(String name) throws Exception {
        try (InputStream in = getAssets().open(name)) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            return out.toByteArray();
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? null : intent.getAction();
        if (ACTION_DETACH.equals(action)) {
            detachOverlay();
        } else if (ACTION_ATTACH.equals(action)) {
            main.removeCallbacks(attach);
            main.postDelayed(attach, ATTACH_DELAY_MS);
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        main.removeCallbacks(tick);
        if (server != null) server.shutdown();
        if (view != null && view.isAttachedToWindow()) wm.removeView(view);
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
