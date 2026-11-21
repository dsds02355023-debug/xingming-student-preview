set -euo pipefail
mkdir -p smoke-results
trap 'adb logcat -d > smoke-results/logcat.txt || true; adb shell dumpsys activity activities > smoke-results/activities.txt || true; adb exec-out screencap -p > smoke-results/screen.png || true' EXIT
apk=smoke-source/app/build/outputs/apk/student/debug/app-student-debug.apk
sdk=${ANDROID_SDK_ROOT:-${ANDROID_HOME:?Android SDK not configured}}
aapt=$(find "$sdk/build-tools" -type f -name aapt | sort -V | tail -n 1)
test -x "$aapt"
badging=$("$aapt" dump badging "$apk")
export STUDENT_TEST_PACKAGE=$(sed -n "s/^package: name='\([^']*\)'.*/\1/p" <<< "$badging")
activity=$(sed -n "s/^launchable-activity: name='\([^']*\)'.*/\1/p" <<< "$badging")
test -n "$STUDENT_TEST_PACKAGE"
test -n "$activity"
printf '%s/%s\n' "$STUDENT_TEST_PACKAGE" "$activity" | tee smoke-results/target.txt
adb logcat -c
adb install "$apk"
adb shell am start -W -n "$STUDENT_TEST_PACKAGE/$activity" | tee smoke-results/launch.txt
grep -q 'Status: ok' smoke-results/launch.txt
sleep 4
adb shell dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity' | grep -F "$STUDENT_TEST_PACKAGE/"
python3 -m venv /tmp/student-back-venv
/tmp/student-back-venv/bin/pip install websocket-client==1.8.0
/tmp/student-back-venv/bin/python .github/scripts/student-back.py | tee smoke-results/back.txt
