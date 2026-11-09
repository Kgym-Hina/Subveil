package io.github.kgymhina.subveil;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;

/** Minimal OpenSubtitles.com REST client used by the standalone web page. */
final class OpenSubtitles {
    private static final String API = "https://api.opensubtitles.com/api/v1";
    static final String USER_AGENT = "Subveil/" + BuildInfo.VERSION + " (+https://github.com/Kgym-Hina/Subveil)";
    private static final int MAX_RESULTS = 30;

    private OpenSubtitles() {}

    static final class Download {
        final String name;
        final byte[] data;

        Download(String name, byte[] data) {
            this.name = name;
            this.data = data;
        }
    }

    /** Returns candidates ranked by exact title match, language preference, then downloads. */
    static JSONArray search(String apiKey, String query, List<String> languages,
                            Integer season, Integer episode) throws Exception {
        // OpenSubtitles redirects requests whose parameters are not sorted and lower-cased.
        Map<String, String> params = new TreeMap<>();
        params.put("languages", String.join(",", sorted(languages)));
        params.put("order_by", "download_count");
        params.put("query", query.trim().toLowerCase(Locale.ROOT));
        if (season != null && episode != null) {
            params.put("type", "episode");
            params.put("season_number", String.valueOf(season));
            params.put("episode_number", String.valueOf(episode));
        }
        StringBuilder url = new StringBuilder(API).append("/subtitles?");
        for (Map.Entry<String, String> e : params.entrySet()) {
            if (url.charAt(url.length() - 1) != '?') url.append('&');
            url.append(e.getKey()).append('=').append(encode(e.getValue()));
        }
        JSONObject body = new JSONObject(new String(request("GET", url.toString(), apiKey, null), StandardCharsets.UTF_8));
        JSONArray data = body.optJSONArray("data");
        String wanted = normalize(query);

        List<JSONObject> results = new ArrayList<>();
        for (int i = 0; data != null && i < data.length(); i++) {
            JSONObject attrs = data.getJSONObject(i).optJSONObject("attributes");
            if (attrs == null) continue;
            JSONArray files = attrs.optJSONArray("files");
            if (files == null || files.length() == 0) continue;
            JSONObject file = files.getJSONObject(0);
            JSONObject feature = attrs.optJSONObject("feature_details");
            boolean titleMatch = false;
            if (feature != null) {
                for (String k : new String[]{"title", "movie_name", "parent_title"}) {
                    if (wanted.equals(normalize(feature.optString(k, "")))) titleMatch = true;
                }
            }
            String lang = attrs.optString("language", "?").toLowerCase(Locale.ROOT);
            JSONObject c = new JSONObject();
            c.put("file_id", file.getLong("file_id"));
            c.put("language", lang);
            c.put("release", attrs.optString("release", file.optString("file_name", query)));
            c.put("downloads", attrs.optInt("download_count", 0));
            c.put("hearing_impaired", attrs.optBoolean("hearing_impaired", false));
            c.put("machine_translated", attrs.optBoolean("machine_translated", false) || attrs.optBoolean("ai_translated", false));
            c.put("title_match", titleMatch);
            int langRank = languages.indexOf(lang);
            c.put("_lang_rank", langRank < 0 ? languages.size() : langRank);
            results.add(c);
        }
        Collections.sort(results, (a, b) -> {
            int r = Boolean.compare(b.optBoolean("title_match"), a.optBoolean("title_match"));
            if (r != 0) return r;
            r = Integer.compare(a.optInt("_lang_rank"), b.optInt("_lang_rank"));
            if (r != 0) return r;
            return Integer.compare(b.optInt("downloads"), a.optInt("downloads"));
        });
        JSONArray out = new JSONArray();
        for (int i = 0; i < results.size() && i < MAX_RESULTS; i++) {
            JSONObject c = results.get(i);
            c.remove("_lang_rank");
            out.put(c);
        }
        return out;
    }

    static Download download(String apiKey, long fileId) throws Exception {
        JSONObject req = new JSONObject().put("file_id", fileId);
        JSONObject resp = new JSONObject(new String(
                request("POST", API + "/download", apiKey, req.toString()), StandardCharsets.UTF_8));
        String link = resp.optString("link", "");
        if (link.isEmpty()) throw new IOException(resp.optString("message", "download link missing"));
        byte[] data = request("GET", link, null, null);
        return new Download(resp.optString("file_name", fileId + ".srt"), data);
    }

    private static byte[] request(String method, String url, String apiKey, String json) throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setRequestMethod(method);
        c.setConnectTimeout(15000);
        c.setReadTimeout(30000);
        c.setRequestProperty("User-Agent", USER_AGENT);
        c.setRequestProperty("Accept", "application/json");
        if (apiKey != null) c.setRequestProperty("Api-Key", apiKey);
        if (json != null) {
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json");
            try (OutputStream out = c.getOutputStream()) {
                out.write(json.getBytes(StandardCharsets.UTF_8));
            }
        }
        int code = c.getResponseCode();
        InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
        byte[] body = in == null ? new byte[0] : readAll(in);
        c.disconnect();
        if (code >= 400) {
            String msg = new String(body, StandardCharsets.UTF_8);
            try {
                msg = new JSONObject(msg).optString("message", msg);
            } catch (Exception ignored) {
            }
            throw new IOException("OpenSubtitles HTTP " + code + ": " + msg);
        }
        return body;
    }

    private static byte[] readAll(InputStream in) throws IOException {
        try (InputStream s = in) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = s.read(buf)) > 0) out.write(buf, 0, n);
            return out.toByteArray();
        }
    }

    private static String encode(String s) throws IOException {
        return URLEncoder.encode(s, "UTF-8").replace("+", "%20");
    }

    private static List<String> sorted(List<String> in) {
        List<String> copy = new ArrayList<>(in);
        Collections.sort(copy);
        return copy;
    }

    static String normalize(String title) {
        return title.toLowerCase(Locale.ROOT).replaceAll("[^\\p{L}\\p{N}]+", " ").trim();
    }
}
