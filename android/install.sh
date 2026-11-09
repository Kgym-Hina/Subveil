#!/bin/sh
# Installs the APK on a TV over ADB, grants the overlay permission and starts the service.
# Usage: ./install.sh [path/to/subveil.apk] [adb-serial]
set -e
PKG=io.github.kgymhina.subveil
APK="${1:-$(ls "$(dirname "$0")"/build/subveil-*.apk | head -n1)}"
ADB="adb${2:+ -s $2}"
$ADB install -r "$APK"
$ADB shell appops set $PKG SYSTEM_ALERT_WINDOW allow
# Some TVs (e.g. Xiaomi) kill an app that owns an overlay when its activity is closed,
# so start the service directly instead of opening the app.
$ADB shell am start-foreground-service -n $PKG/.OverlayService
sleep 2
IP=$($ADB shell ip -4 addr show wlan0 2>/dev/null | sed -n 's/.*inet \([0-9.]*\).*/\1/p' | head -n1)
[ -n "$IP" ] || IP=$($ADB shell ip -4 addr show eth0 2>/dev/null | sed -n 's/.*inet \([0-9.]*\).*/\1/p' | head -n1)
echo "Subveil is running: http://${IP:-<tv-ip>}:8765"
