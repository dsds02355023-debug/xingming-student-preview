#!/usr/bin/env bash
set -eu
cd "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"

# All commands run in one Bash process so variables and exports persist.
apk="${STUDENT_PREVIEW_APK_PATH:?STUDENT_PREVIEW_APK_PATH is required}"
if [ ! -s "$apk" ]; then
  echo "Preview APK missing at: $apk"
  echo "PWD: $(pwd)"
  echo "GITHUB_WORKSPACE: $GITHUB_WORKSPACE"
  ls -la "$GITHUB_WORKSPACE" || true
  find "$GITHUB_WORKSPACE" -maxdepth 5 -name 'xingming-student-preview-v1.0.42.apk' -print || true
  exit 1
fi
metadata=$("$ANDROID_HOME/build-tools/35.0.0/aapt" dump badging "$apk")
package=$(printf '%s\n' "$metadata" | sed -n "s/^package: name=\x27\([^\x27]*\)\x27.*/\1/p")
activity=$(printf '%s\n' "$metadata" | sed -n "s/^launchable-activity: name=\x27\([^\x27]*\)\x27.*/\1/p")
test "$package" = "com.xingming.apps.student.preview"
test -n "$activity"
adb install "$apk"
adb shell am start -W -n "$package/$activity"
python3 -m venv /tmp/student-preview-venv
/tmp/student-preview-venv/bin/pip install websocket-client==1.8.0
export STUDENT_TEST_PACKAGE="$package"
/tmp/student-preview-venv/bin/python private-source/.github/scripts/student-settings-smoke.py
/tmp/student-preview-venv/bin/python private-source/.github/scripts/student-rules-smoke.py
/tmp/student-preview-venv/bin/python private-source/.github/scripts/student-home-back-smoke.py
STUDENT_EXPECTED_VERSION_NAME=1.0.42 /tmp/student-preview-venv/bin/python private-source/.github/scripts/student-result-layout-smoke.py
