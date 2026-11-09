package io.github.kgymhina.subveil;

import android.content.Context;

/** Apple TV support is only built into the standalone edition. */
final class AppleTv {
    static boolean supported() {
        return false;
    }

    AppleTv(Context context) {}

    String scan() {
        throw new UnsupportedOperationException("Apple TV support is not available in this edition");
    }

    String pairBegin(String id, String address) {
        return scan();
    }

    String pairFinish(String pin) {
        return scan();
    }

    void connect(String id, String address, String credentials) {
        scan();
    }

    void disconnect() {}

    String status() {
        return "{\"status\":\"idle\"}";
    }
}
