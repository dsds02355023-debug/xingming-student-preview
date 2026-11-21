#!/usr/bin/env bash
set -Eeuo pipefail
cd "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
mkdir -p smoke-results
exec > >(tee -a smoke-results/acceptance.log) 2>&1
stage=initialization
finish() {
  local rc=$?
  trap - EXIT
  set +e
  printf '%s END stage=%s exit=%s\n' "$(date -u +%FT%TZ)" "$stage" "$rc" | tee smoke-results/exit-status.txt
  timeout -k 5s 20s adb devices -l > smoke-results/adb-devices.txt 2>&1
  timeout -k 5s 20s adb logcat -d -v threadtime > smoke-results/logcat.txt 2>&1
  timeout -k 5s 20s adb shell dumpsys activity activities > smoke-results/activities.txt 2>&1
  timeout -k 5s 20s adb exec-out screencap -p > smoke-results/final-screen.png 2> smoke-results/screenshot-error.txt
  exit "$rc"
}
trap finish EXIT
trap 'rc=$?; printf "ERROR stage=%s line=%s exit=%s command=%s\n" "$stage" "$LINENO" "$rc" "$BASH_COMMAND" >&2' ERR
run_stage() {
  stage=$1
  local limit=$2
  shift 2
  printf '%s START %s timeout=%s\n' "$(date -u +%FT%TZ)" "$stage" "$limit"
  timeout --signal=TERM --kill-after=10s "$limit" "$@"
  printf '%s PASS %s\n' "$(date -u +%FT%TZ)" "$stage"
}
printf '%s ACCEPTANCE SCRIPT ENTERED workspace=%s\n' "$(date -u +%FT%TZ)" "$PWD"
stage=apk-validation
apk="${STUDENT_PREVIEW_APK_PATH:?STUDENT_PREVIEW_APK_PATH is required}"
if [ ! -s "$apk" ]; then
  echo "Preview APK missing at: $apk"
  ls -la "$GITHUB_WORKSPACE" || true
  find "$GITHUB_WORKSPACE" -maxdepth 5 -name 'xingming-student-preview-v1.0.42.apk' -print || true
  exit 1
fi
sha256sum "$apk" | tee smoke-results/apk-sha256.txt
metadata=$(timeout -k 5s 30s "$ANDROID_HOME/build-tools/35.0.0/aapt" dump badging "$apk")
printf '%s\n' "$metadata" > smoke-results/apk-badging.txt
package=$(printf '%s\n' "$metadata" | sed -n "s/^package: name='\([^']*\)'.*/\1/p")
activity=$(printf '%s\n' "$metadata" | sed -n "s/^launchable-activity: name='\([^']*\)'.*/\1/p")
test "$package" = "com.xingming.apps.student.preview"
test -n "$activity"
run_stage adb-ready 60s adb wait-for-device
run_stage apk-install 180s adb install -r "$apk"
run_stage app-launch 60s adb shell am start -W -n "$package/$activity"
run_stage python-venv 60s python3 -m venv /tmp/student-preview-venv
run_stage python-dependencies 180s /tmp/student-preview-venv/bin/pip install --disable-pip-version-check --timeout 30 --retries 2 websocket-client==1.8.0
export STUDENT_TEST_PACKAGE="$package"
export STUDENT_EXPECTED_VERSION_NAME=1.0.42
printf 'test\texit_code\n' > smoke-results/test-status.tsv
failed=0
for test_name in student-settings-smoke student-rules-smoke student-home-back-smoke student-result-layout-smoke; do
  stage="$test_name"
  printf '%s START %s timeout=300s\n' "$(date -u +%FT%TZ)" "$stage"
  if timeout --signal=TERM --kill-after=10s 300s /tmp/student-preview-venv/bin/python -u "private-source/.github/scripts/$test_name.py" > "smoke-results/$test_name.log" 2>&1; then
    rc=0
  else
    rc=$?
    failed=1
  fi
  cat "smoke-results/$test_name.log"
  printf '%s\t%s\n' "$test_name" "$rc" >> smoke-results/test-status.tsv
  printf '%s END %s exit=%s\n' "$(date -u +%FT%TZ)" "$stage" "$rc"
done
stage=completed
exit "$failed"
