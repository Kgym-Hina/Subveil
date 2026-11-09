#!/bin/sh
# Builds both editions with Gradle and copies the APKs to build/.
#
# Signing: set SUBVEIL_KEYSTORE, SUBVEIL_KEYSTORE_PASS and SUBVEIL_KEY_ALIAS for a release
# build; otherwise a local debug keystore is generated and used.
# VARIANT=ha or VARIANT=standalone builds only that edition.
set -e
cd "$(dirname "$0")"
if [ -z "$JAVA_HOME" ] && [ -d /opt/homebrew/opt/openjdk@17 ]; then
  export JAVA_HOME=/opt/homebrew/opt/openjdk@17
fi
export ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"
[ -f debug.keystore ] || keytool -genkeypair -keystore debug.keystore -storepass android \
  -keypass android -alias debug -keyalg RSA -validity 10000 -dname "CN=Subveil Debug" >/dev/null 2>&1

case "${VARIANT:-all}" in
  ha) TASKS="assembleHaRelease" ;;
  standalone) TASKS="assembleStandaloneRelease" ;;
  all) TASKS="assembleHaRelease assembleStandaloneRelease" ;;
  *) echo "Unknown VARIANT: $VARIANT" >&2; exit 1 ;;
esac
case "$TASKS" in
  *Standalone*)
    # Chaquopy only installs wheels, and zeroconf ships no pure-Python wheel. Built
    # without Cython it is pure Python, so build it here and retag it.
    ZC=$(sed -n 's/^val zeroconfVersion = "\(.*\)"/\1/p' build.gradle.kts)
    WHL="build/wheels/zeroconf-$ZC-py3-none-any.whl"
    if [ ! -f "$WHL" ]; then
      PY="${SUBVEIL_BUILD_PYTHON:-python3}"
      rm -rf build/wheels build/wheel-venv && mkdir -p build/wheels
      "$PY" -m venv build/wheel-venv
      build/wheel-venv/bin/pip -q install wheel
      SKIP_CYTHON=1 build/wheel-venv/bin/pip -q wheel --no-deps --no-binary zeroconf \
        "zeroconf==$ZC" -w build/wheels
      build/wheel-venv/bin/python -m wheel tags --remove --python-tag py3 --abi-tag none \
        --platform-tag any build/wheels/zeroconf-$ZC-*.whl >/dev/null
    fi
    ;;
esac

# One Gradle run per edition: the Python plugin is only applied to standalone builds.
for task in $TASKS; do
  ./gradlew --no-daemon -q "$task"
done

VERSION=$(sed -n 's/^val appVersion = "\(.*\)"/\1/p' build.gradle.kts)
mkdir -p build
for f in build/outputs/apk/ha/release/*.apk; do
  [ -f "$f" ] && cp "$f" "build/subveil-$VERSION.apk" && echo "Built $(pwd)/build/subveil-$VERSION.apk"
done
for f in build/outputs/apk/standalone/release/*.apk; do
  [ -f "$f" ] && cp "$f" "build/subveil-standalone-$VERSION.apk" && echo "Built $(pwd)/build/subveil-standalone-$VERSION.apk"
done
true
