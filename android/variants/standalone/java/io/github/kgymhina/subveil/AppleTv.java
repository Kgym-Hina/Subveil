package io.github.kgymhina.subveil;

import android.content.Context;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

/** Talks to the Apple TV through pyatv (see variants/standalone/python/subveil_atv.py). */
final class AppleTv {
    private final Context context;
    private PyObject module;

    static boolean supported() {
        return true;
    }

    AppleTv(Context context) {
        this.context = context.getApplicationContext();
    }

    /** Starting Python and importing pyatv takes a few seconds; do not call on the main thread. */
    private synchronized PyObject module() {
        if (module == null) {
            if (!Python.isStarted()) Python.start(new AndroidPlatform(context));
            module = Python.getInstance().getModule("subveil_atv");
        }
        return module;
    }

    String scan() {
        return module().callAttr("scan", 5).toString();
    }

    String pairBegin(String id, String address) {
        return module().callAttr("pair_begin", id, address).toString();
    }

    String pairFinish(String pin) {
        return module().callAttr("pair_finish", pin).toString();
    }

    void connect(String id, String address, String credentials) {
        module().callAttr("connect", id, address, credentials);
    }

    void disconnect() {
        module().callAttr("disconnect");
    }

    String status() {
        return module().callAttr("status").toString();
    }
}
