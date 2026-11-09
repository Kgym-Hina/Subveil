package io.github.kgymhina.subveil;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * Lets other apps (automation apps, voice-assistant routines, `adb shell am broadcast`) send
 * commands. The commands are forwarded to the running service.
 */
public class CommandReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent.getAction() == null || !intent.getAction().startsWith(OverlayService.COMMAND_PREFIX)) return;
        Intent forward = new Intent(context, OverlayService.class)
                .setAction(intent.getAction())
                .putExtras(intent);
        context.startForegroundService(forward);
    }
}
