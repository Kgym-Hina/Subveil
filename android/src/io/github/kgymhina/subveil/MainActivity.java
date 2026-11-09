package io.github.kgymhina.subveil;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class MainActivity extends Activity {
    private static final int QR_SIZE_PX = 420;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setBackgroundColor(Color.BLACK);

        TextView tv = new TextView(this);
        tv.setTextColor(Color.WHITE);
        tv.setTextSize(24);
        tv.setGravity(Gravity.CENTER);
        root.addView(tv);

        StringBuilder sb = new StringBuilder(getString(R.string.app_name)).append("\n\n");
        if (Settings.canDrawOverlays(this)) {
            sb.append(getString(R.string.main_running)).append('\n');
        } else {
            sb.append(getString(R.string.main_no_permission, getPackageName())).append('\n');
        }
        List<String> urls = new ArrayList<>();
        for (String ip : localIps()) urls.add("http://" + ip + ":" + OverlayService.PORT);
        sb.append('\n').append(getString(R.string.main_address)).append('\n');
        for (String url : urls) sb.append(url).append('\n');
        tv.setText(sb.toString());

        Bitmap qr = urls.isEmpty() ? null : QrCode.create(urls.get(0), QR_SIZE_PX);
        if (qr != null) {
            ImageView iv = new ImageView(this);
            iv.setImageBitmap(qr);
            root.addView(iv, new LinearLayout.LayoutParams(QR_SIZE_PX, QR_SIZE_PX));
        }
        setContentView(root);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (Settings.canDrawOverlays(this)) {
            startForegroundService(new Intent(this, OverlayService.class).setAction(OverlayService.ACTION_DETACH));
        }
    }

    @Override
    protected void onPause() {
        if (Settings.canDrawOverlays(this)) {
            startForegroundService(new Intent(this, OverlayService.class).setAction(OverlayService.ACTION_ATTACH));
        }
        super.onPause();
    }

    /** Wi-Fi and Ethernet addresses first, since the QR code uses the first one. */
    private static List<String> localIps() {
        List<String> preferred = new ArrayList<>();
        List<String> other = new ArrayList<>();
        try {
            for (NetworkInterface ni : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                if (!ni.isUp() || ni.isLoopback()) continue;
                boolean lan = ni.getName().startsWith("wlan") || ni.getName().startsWith("eth");
                for (InetAddress a : Collections.list(ni.getInetAddresses())) {
                    if (a instanceof Inet4Address) (lan ? preferred : other).add(a.getHostAddress());
                }
            }
        } catch (Exception ignored) {
        }
        preferred.addAll(other);
        return preferred;
    }
}
