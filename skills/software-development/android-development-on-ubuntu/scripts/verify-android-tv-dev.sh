#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${1:-$HOME/code/android-tv-test}"
AVD_NAME="${2:-AndroidTV_API34}"
SDK_IMAGE="${3:-system-images;android-34;android-tv;x86}"

pass() { printf "\033[1;32m[PASS]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[WARN]\033[0m %s\n" "$*"; }
fail() { printf "\033[1;31m[FAIL]\033[0m %s\n" "$*"; exit 1; }
section() { echo; printf "\033[1;36m== %s ==\033[0m\n" "$*"; }

section "Load shell environment"
source "$HOME/.profile" >/dev/null 2>&1 || true
hash -r
pass "Shell config loaded"

section "Verify required commands"
for cmd in java sdkmanager adb gradle avdmanager emulator; do
  command -v "$cmd" >/dev/null 2>&1 || fail "$cmd not found in PATH"
  pass "$cmd -> $(command -v "$cmd")"
done

section "Verify Java"
JAVA_VERSION="$(java -version 2>&1 | head -n1)"
echo "$JAVA_VERSION"
echo "$JAVA_VERSION" | grep -q '"17\.' || fail "Java 17 not detected"
pass "OpenJDK 17 detected"

section "Verify environment"
echo "JAVA_HOME=${JAVA_HOME:-}"
echo "ANDROID_SDK_ROOT=${ANDROID_SDK_ROOT:-}"
echo "GRADLE_HOME=${GRADLE_HOME:-}"
[ -n "${ANDROID_SDK_ROOT:-}" ] || fail "ANDROID_SDK_ROOT is empty"
[ -d "$ANDROID_SDK_ROOT" ] || fail "ANDROID_SDK_ROOT directory missing"
pass "Android SDK root exists"

section "Verify tool versions"
sdkmanager --version || fail "sdkmanager failed"
adb version || fail "adb version failed"
gradle -v | sed -n '1,14p'
pass "sdkmanager/adb/gradle responded"

section "Verify installed SDK packages"
INSTALLED="$(sdkmanager --list_installed)"
echo "$INSTALLED" | grep -q 'platform-tools' || fail "platform-tools missing"
echo "$INSTALLED" | grep -q 'platforms;android-34' || fail "platforms;android-34 missing"
echo "$INSTALLED" | grep -q 'build-tools;34.0.0' || fail "build-tools;34.0.0 missing"
echo "$INSTALLED" | grep -q 'sources;android-34' || fail "sources;android-34 missing"
echo "$INSTALLED" | grep -q "$SDK_IMAGE" || fail "$SDK_IMAGE missing"
pass "Required SDK packages are installed"

section "Check acceleration reality"
emulator -accel-check || true
if [ ! -e /dev/kvm ]; then
  warn "/dev/kvm missing; emulator may stay adb-offline in software mode"
fi
if ! egrep -q '(vmx|svm)' /proc/cpuinfo; then
  warn "No VMX/SVM flags visible in /proc/cpuinfo"
fi

section "Ensure AVD exists"
if emulator -list-avds | grep -qx "$AVD_NAME"; then
  pass "AVD already exists: $AVD_NAME"
else
  echo "no" | avdmanager create avd -n "$AVD_NAME" -k "$SDK_IMAGE" -d tv_1080p || fail "Failed to create AVD"
  pass "Created AVD: $AVD_NAME"
fi

section "Verify sample project exists"
[ -d "$PROJECT_DIR" ] || fail "Project directory missing: $PROJECT_DIR"
[ -f "$PROJECT_DIR/settings.gradle.kts" ] || fail "settings.gradle.kts missing"
[ -f "$PROJECT_DIR/app/build.gradle.kts" ] || fail "app/build.gradle.kts missing"
pass "Sample project files exist"

section "Generate wrapper if needed and build"
cd "$PROJECT_DIR"
if [ ! -x ./gradlew ]; then
  gradle wrapper --gradle-version 8.10.2 || fail "Failed to generate gradle wrapper"
fi
./gradlew --version || fail "gradlew --version failed"
./gradlew assembleDebug || fail "assembleDebug failed"
APK_PATH="$PROJECT_DIR/app/build/outputs/apk/debug/app-debug.apk"
[ -f "$APK_PATH" ] || fail "APK not found at $APK_PATH"
pass "APK exists: $APK_PATH"

section "Manual emulator runtime verification"
cat <<EOF
Launch emulator manually and verify that adb reaches 'device', not merely 'offline':

  emulator -avd $AVD_NAME -accel off -gpu swiftshader_indirect -no-snapshot-load -no-snapshot-save -wipe-data
  adb devices -l
  adb wait-for-device
  adb shell getprop sys.boot_completed

If adb remains 'offline' for minutes on a host without /dev/kvm, record it as a host limitation, not a successful emulator verification.
EOF
