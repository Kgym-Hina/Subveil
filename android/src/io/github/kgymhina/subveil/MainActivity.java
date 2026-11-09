package io.github.kgymhina.subveil;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.widget.TextView;

import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.util.Collections;

public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        TextView tv = new TextView(this);
        tv.setTextColor(Color.WHITE);
        tv.setBackgroundColor(Color.BLACK);
        tv.setTextSize(24);
        tv.setGravity(Gravity.CENTER);
        setContentView(tv);

        StringBuilder sb = new StringBuilder(getString(R.string.app_name)).append("\n\n");
        if (Settings.canDrawOverlays(this)) {
            sb.append(getString(R.string.main_running)).append('\n');
        } else {
            sb.append(getString(R.string.main_no_permission, getPackageName())).append('\n');
        }
        sb.append('\n').append(getString(R.string.main_address)).append('\n');
        for (String ip : localIps()) sb.append("http://").append(ip).append(':').append(OverlayService.PORT).append('\n');
        tv.setText(sb.toString());
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

    private static Iterable<String> localIps() {
        java.util.List<String> ips = new java.util.ArrayList<>();
        try {
            for (NetworkInterface ni : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                if (!ni.isUp() || ni.isLoopback()) continue;
                for (InetAddress a : Collections.list(ni.getInetAddresses())) {
                    if (a instanceof Inet4Address) ips.add(a.getHostAddress());
                }
            }
        } catch (Exception ignored) {
        }
        return ips;
    }
}
