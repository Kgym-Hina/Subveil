#!/bin/sh
# Builds the APK with the Android SDK build tools directly (no Gradle).
#
# Signing: set SUBVEIL_KEYSTORE, SUBVEIL_KEYSTORE_PASS and SUBVEIL_KEY_ALIAS for a release
# build; otherwise a local debug keystore is generated and used.
set -e
cd "$(dirname "$0")"
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"
BT="$SDK/build-tools/${BUILD_TOOLS_VERSION:-35.0.0}"
JAR="$SDK/platforms/android-34/android.jar"
if [ -z "$JAVA_HOME" ] && [ -d /opt/homebrew/opt/openjdk@17 ]; then
  export JAVA_HOME=/opt/homebrew/opt/openjdk@17
fi
[ -n "$JAVA_HOME" ] && export PATH="$JAVA_HOME/bin:$PATH"

VERSION=$(sed -n 's/.*android:versionName="\([^"]*\)".*/\1/p' AndroidManifest.xml)
OUT="build/subveil-$VERSION.apk"

rm -rf build && mkdir -p build/classes build/dex build/gen
"$BT/aapt2" compile --dir res -o build/res.zip
"$BT/aapt2" link -o build/base.apk -I "$JAR" --manifest AndroidManifest.xml -A assets \
  --java build/gen build/res.zip
javac -Xlint:-options --release 8 -encoding UTF-8 -classpath "$JAR" -d build/classes \
  $(find src build/gen -name '*.java')
"$BT/d8" --release --min-api 26 --lib "$JAR" --output build/dex $(find build/classes -name '*.class')
cp build/base.apk build/unsigned.apk
(cd build/dex && zip -q ../unsigned.apk classes.dex)
"$BT/zipalign" -f 4 build/unsigned.apk build/aligned.apk

if [ -n "$SUBVEIL_KEYSTORE" ]; then
  "$BT/apksigner" sign --ks "$SUBVEIL_KEYSTORE" --ks-pass env:SUBVEIL_KEYSTORE_PASS \
    --ks-key-alias "${SUBVEIL_KEY_ALIAS:-subveil}" --out "$OUT" build/aligned.apk
else
  [ -f debug.keystore ] || keytool -genkeypair -keystore debug.keystore -storepass android \
    -keypass android -alias debug -keyalg RSA -validity 10000 -dname "CN=Subveil Debug" >/dev/null 2>&1
  "$BT/apksigner" sign --ks debug.keystore --ks-pass pass:android --out "$OUT" build/aligned.apk
fi
echo "Built $(pwd)/$OUT"
