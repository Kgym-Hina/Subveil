package io.github.kgymhina.subveil;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        Log.i(OverlayService.TAG, "starting on " + intent.getAction());
        try {
            context.startForegroundService(new Intent(context, OverlayService.class));
        } catch (Exception e) {
            Log.e(OverlayService.TAG, "failed to start service", e);
        }
    }
}
