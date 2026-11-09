package io.github.kgymhina.subveil;

import android.util.Log;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/** Minimal blocking HTTP/1.1 server; one thread per connection, Connection: close. */
final class HttpServer extends Thread {
    private static final String TAG = "Subveil";
    private static final int MAX_BODY = 20 * 1024 * 1024;

    interface Handler {
        Response handle(Request r) throws Exception;
    }

    static final class Request {
        String method;
        String path;
        final Map<String, String> query = new HashMap<>();
        byte[] body = new byte[0];

        JSONObject json() throws Exception {
            String s = new String(body, StandardCharsets.UTF_8).trim();
            return s.isEmpty() ? new JSONObject() : new JSONObject(s);
        }
    }

    static final class Response {
        final int code;
        final String type;
        final byte[] body;

        Response(int code, String type, byte[] body) {
            this.code = code;
            this.type = type;
            this.body = body;
        }

        static Response json(int code, JSONObject o) {
            return new Response(code, "application/json; charset=utf-8", o.toString().getBytes(StandardCharsets.UTF_8));
        }

        static Response error(int code, String msg) {
            JSONObject o = new JSONObject();
            try {
                o.put("ok", false);
                o.put("error", msg);
            } catch (Exception ignored) {
            }
            return json(code, o);
        }
    }

    private final int port;
    private final Handler handler;
    private volatile boolean running = true;
    private ServerSocket socket;

    HttpServer(int port, Handler handler) {
        super("http-server");
        this.port = port;
        this.handler = handler;
    }

    @Override
    public void run() {
        try {
            socket = new ServerSocket();
            socket.setReuseAddress(true);
            socket.bind(new InetSocketAddress(port));
            Log.i(TAG, "listening on " + port);
            while (running) {
                Socket s = socket.accept();
                new Thread(() -> serve(s), "http-conn").start();
            }
        } catch (IOException e) {
            if (running) Log.e(TAG, "server stopped", e);
        }
    }

    void shutdown() {
        running = false;
        try {
            if (socket != null) socket.close();
        } catch (IOException ignored) {
        }
    }

    private void serve(Socket s) {
        try (Socket sock = s) {
            sock.setSoTimeout(15000);
            InputStream in = new BufferedInputStream(sock.getInputStream());
            String requestLine = readLine(in);
            if (requestLine == null || requestLine.isEmpty()) return;
            String[] parts = requestLine.split(" ");
            if (parts.length < 2) return;

            int length = 0;
            String line;
            while ((line = readLine(in)) != null && !line.isEmpty()) {
                int colon = line.indexOf(':');
                if (colon > 0 && line.substring(0, colon).trim().toLowerCase(Locale.ROOT).equals("content-length")) {
                    length = Integer.parseInt(line.substring(colon + 1).trim());
                }
            }
            OutputStream out = sock.getOutputStream();
            if (length > MAX_BODY) {
                write(out, Response.error(413, "body too large"));
                return;
            }

            Request req = new Request();
            req.method = parts[0].toUpperCase(Locale.ROOT);
            String target = parts[1];
            int q = target.indexOf('?');
            req.path = q < 0 ? target : target.substring(0, q);
            if (q >= 0) {
                for (String kv : target.substring(q + 1).split("&")) {
                    if (kv.isEmpty()) continue;
                    int eq = kv.indexOf('=');
                    String k = URLDecoder.decode(eq < 0 ? kv : kv.substring(0, eq), "UTF-8");
                    String v = eq < 0 ? "" : URLDecoder.decode(kv.substring(eq + 1), "UTF-8");
                    req.query.put(k, v);
                }
            }
            req.body = readFully(in, length);

            Response resp;
            if (req.method.equals("OPTIONS")) {
                resp = new Response(204, "text/plain", new byte[0]);
            } else {
                try {
                    resp = handler.handle(req);
                } catch (Exception e) {
                    Log.w(TAG, "request failed: " + requestLine, e);
                    resp = Response.error(400, String.valueOf(e.getMessage()));
                }
            }
            write(out, resp);
        } catch (Exception e) {
            Log.w(TAG, "connection error", e);
        }
    }

    private static String readLine(InputStream in) throws IOException {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        int c;
        while ((c = in.read()) != -1) {
            if (c == '\n') break;
            if (c != '\r') buf.write(c);
        }
        if (c == -1 && buf.size() == 0) return null;
        return new String(buf.toByteArray(), StandardCharsets.ISO_8859_1);
    }

    private static byte[] readFully(InputStream in, int length) throws IOException {
        byte[] b = new byte[length];
        int off = 0;
        while (off < length) {
            int n = in.read(b, off, length - off);
            if (n < 0) throw new IOException("unexpected end of body");
            off += n;
        }
        return b;
    }

    private static void write(OutputStream out, Response r) throws IOException {
        String head = "HTTP/1.1 " + r.code + " " + (r.code < 400 ? "OK" : "Error") + "\r\n"
                + "Content-Type: " + r.type + "\r\n"
                + "Content-Length: " + r.body.length + "\r\n"
                + "Access-Control-Allow-Origin: *\r\n"
                + "Access-Control-Allow-Headers: *\r\n"
                + "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
                + "Connection: close\r\n\r\n";
        out.write(head.getBytes(StandardCharsets.ISO_8859_1));
        out.write(r.body);
        out.flush();
    }
}
