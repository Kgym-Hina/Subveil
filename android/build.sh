#!/bin/sh
# Builds the APK with the Android SDK build tools directly (no Gradle).
#
# Variant: VARIANT=ha (default, controlled by Home Assistant) or VARIANT=standalone
# (separate package with a full control page served by the app itself).
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

VARIANT="${VARIANT:-ha}"
VERSION=$(sed -n 's/.*android:versionName="\([^"]*\)".*/\1/p' AndroidManifest.xml)
B="build/$VARIANT"
case "$VARIANT" in
  ha)
    OUT="build/subveil-$VERSION.apk"
    STANDALONE=false
    ;;
  standalone)
    OUT="build/subveil-standalone-$VERSION.apk"
    STANDALONE=true
    ;;
  *) echo "Unknown VARIANT: $VARIANT" >&2; exit 1 ;;
esac

rm -rf "$B" "$OUT" && mkdir -p "$B/classes" "$B/dex" "$B/gen/io/github/kgymhina/subveil"
cat > "$B/gen/io/github/kgymhina/subveil/BuildInfo.java" <<JAVA
package io.github.kgymhina.subveil;

final class BuildInfo {
    static final String VERSION = "$VERSION";
    static final boolean STANDALONE = $STANDALONE;

    private BuildInfo() {}
}
JAVA

"$BT/aapt2" compile --dir res -o "$B/res.zip"
if [ "$VARIANT" = standalone ]; then
  "$BT/aapt2" compile --dir variants/standalone/res -o "$B/res-variant.zip"
  "$BT/aapt2" link -o "$B/base.apk" -I "$JAR" --manifest AndroidManifest.xml \
    -A variants/standalone/assets --rename-manifest-package io.github.kgymhina.subveil.standalone \
    --java "$B/gen" "$B/res.zip" -R "$B/res-variant.zip" --auto-add-overlay
else
  "$BT/aapt2" link -o "$B/base.apk" -I "$JAR" --manifest AndroidManifest.xml -A assets \
    --java "$B/gen" "$B/res.zip"
fi
javac -Xlint:-options --release 8 -encoding UTF-8 -classpath "$JAR" -d "$B/classes" \
  $(find src "$B/gen" -name '*.java')
"$BT/d8" --release --min-api 26 --lib "$JAR" --output "$B/dex" $(find "$B/classes" -name '*.class')
cp "$B/base.apk" "$B/unsigned.apk"
(cd "$B/dex" && zip -q ../unsigned.apk classes.dex)
"$BT/zipalign" -f 4 "$B/unsigned.apk" "$B/aligned.apk"

if [ -n "$SUBVEIL_KEYSTORE" ]; then
  "$BT/apksigner" sign --ks "$SUBVEIL_KEYSTORE" --ks-pass env:SUBVEIL_KEYSTORE_PASS \
    --ks-key-alias "${SUBVEIL_KEY_ALIAS:-subveil}" --out "$OUT" "$B/aligned.apk"
else
  [ -f debug.keystore ] || keytool -genkeypair -keystore debug.keystore -storepass android \
    -keypass android -alias debug -keyalg RSA -validity 10000 -dname "CN=Subveil Debug" >/dev/null 2>&1
  "$BT/apksigner" sign --ks debug.keystore --ks-pass pass:android --out "$OUT" "$B/aligned.apk"
fi
echo "Built $(pwd)/$OUT"
