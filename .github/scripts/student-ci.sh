#!/usr/bin/env bash
set -Eeuo pipefail
cd "${GITHUB_WORKSPACE:?}"
mkdir -p smoke-results
mode=${1:?stage required}
exec > >(tee -a "smoke-results/stage-$mode.log") 2>&1
trap 'rc=$?; printf "::error title=Student CI failure::stage=%s line=%s exit=%s command=%s\n" "$mode" "$LINENO" "$rc" "$BASH_COMMAND" >&2' ERR
export PATH="${ANDROID_HOME:?}/platform-tools:$ANDROID_HOME/emulator:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
printf '%s START stage=%s\n' "$(date -u +%FT%TZ)" "$mode"
apk="$GITHUB_WORKSPACE/xingming-student-preview-v1.0.42.apk"
case "$mode" in
build)
  git -C private-source rev-parse HEAD > smoke-results/source-commit.txt
  printf '%s\n' "${GITHUB_SHA:-unknown}" > smoke-results/workflow-commit.txt
  for attempt in 1 2 3; do
    log="smoke-results/gradle-$attempt.log"
    started=$SECONDS
    timeout --kill-after=15s 180s gradle -p smoke-source --no-daemon --console=plain assembleStudentDebug > "$log" 2>&1 &
    pid=$!
    while kill -0 "$pid" 2>/dev/null; do
      printf '%s Gradle process active attempt=%s elapsed=%ss log_bytes=%s\n' "$(date -u +%FT%TZ)" "$attempt" "$((SECONDS-started))" "$(wc -c < "$log")"
      tail -n 5 "$log"
      sleep 15
    done
    if wait "$pid"; then rc=0; else rc=$?; fi
    cat "$log"
    printf '%s\t%s\t%s\n' "$attempt" "$rc" "$((SECONDS-started))" >> smoke-results/build-attempts.tsv
    if [ "$rc" -eq 0 ]; then break; fi
    if [ "$rc" -eq 124 ] || [ "$attempt" -eq 3 ] || ! grep -Eiq 'HTTP[^[:cntrl:]]*(429|502|503|504)|status code[^[:cntrl:]]*(429|502|503|504)|Connection reset|Read timed out|Temporary failure in name resolution' "$log"; then
      exit "$rc"
    fi
    sleep "$((attempt*30))"
  done
  test -s smoke-source/app/build/outputs/apk/student/debug/app-student-debug.apk
  cp smoke-source/app/build/outputs/apk/student/debug/app-student-debug.apk "$apk"
  ;;
verify)
  test -s "$apk"
  timeout -k 5s 30s "$ANDROID_HOME/build-tools/35.0.0/aapt" dump badging "$apk" > smoke-results/apk-badging.txt
  grep -F "package: name='com.xingming.apps.student.preview' versionCode='42'" smoke-results/apk-badging.txt
  grep -F "versionName='1.0.42'" smoke-results/apk-badging.txt
  python3 -c 'import pathlib,zipfile,hashlib; p=pathlib.Path("smoke-source/app/src/student/assets/index.html"); a=pathlib.Path("xingming-student-preview-v1.0.42.apk"); z=zipfile.ZipFile(a); data=z.read("assets/index.html"); assert data==p.read_bytes(), "APK HTML differs from integrated obfuscated source"; print("APK HTML SHA256",hashlib.sha256(data).hexdigest())' | tee smoke-results/apk-html-verification.txt
  sha256sum "$apk" | tee smoke-results/apk-sha256.txt
  ;;
kvm)
  id
  test -c /dev/kvm
  echo 'KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"' | sudo tee /etc/udev/rules.d/99-kvm4all.rules
  sudo udevadm control --reload-rules
  sudo udevadm trigger --name-match=kvm
  sudo udevadm settle --timeout=30
  ls -l /dev/kvm
  test -r /dev/kvm
  test -w /dev/kvm
  ;;
sdk)
  manager=$(command -v sdkmanager || true)
  if [ -z "$manager" ]; then manager="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"; fi
  set +e
  yes | timeout -k 5s 45s "$manager" --licenses > smoke-results/sdk-licenses.log 2>&1
  rc=${PIPESTATUS[1]}
  set -e
  test "$rc" -eq 0
  timeout -k 10s 180s "$manager" 'platform-tools' 'emulator' 'system-images;android-35;default;x86_64' 2>&1 | tee smoke-results/sdk-install.log
  timeout -k 5s 30s "$ANDROID_HOME/emulator/emulator" -accel-check 2>&1 | tee smoke-results/kvm-accel-check.log
  avdmanager=$(command -v avdmanager || true)
  if [ -z "$avdmanager" ]; then avdmanager="$ANDROID_HOME/cmdline-tools/latest/bin/avdmanager"; fi
  timeout -k 5s 30s "$avdmanager" create avd --force --name student-preview --package 'system-images;android-35;default;x86_64' --device pixel_2 <<< no
  python3 -m venv /tmp/student-preview-venv
  timeout -k 5s 30s /tmp/student-preview-venv/bin/pip install --disable-pip-version-check --timeout 10 --retries 1 websocket-client==1.8.0
  ;;
boot)
  if [ ! -x "$ANDROID_HOME/platform-tools/adb" ]; then
    echo "::error::ADB executable missing at $ANDROID_HOME/platform-tools/adb"
    exit 127
  fi
  command -v adb
  timeout -k 2s 10s adb version
  timeout -k 5s 15s adb start-server
  nohup "$ANDROID_HOME/emulator/emulator" -avd student-preview -port 5554 -accel on -no-window -gpu swiftshader_indirect -no-snapshot -noaudio -no-boot-anim -camera-back none -camera-front none -memory 2048 -cores 2 > smoke-results/emulator-stdout.log 2> smoke-results/emulator-stderr.log < /dev/null &
  pid=$!
  echo "$pid" > smoke-results/emulator.pid
  deadline=$((SECONDS+300))
  ready=0
  while [ "$SECONDS" -lt "$deadline" ]; do
    if ! kill -0 "$pid" 2>/dev/null; then
      cat smoke-results/emulator-stderr.log
      echo '::error::Emulator process exited before boot completed.'
      exit 1
    fi
    state=$(timeout -k 1s 3s adb get-state 2>/dev/null || true)
    boot=$(timeout -k 1s 3s adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)
    printf '%s adb=%s sys.boot_completed=%s\n' "$(date -u +%FT%TZ)" "$state" "$boot"
    if [ "$state" = device ] && [ "$boot" = 1 ]; then ready=1; break; fi
    sleep 10
  done
  if [ "$ready" -ne 1 ]; then echo '::error::Emulator boot exceeded 300 seconds.'; exit 124; fi
  for setting in window_animation_scale transition_animation_scale animator_duration_scale; do timeout -k 2s 5s adb shell settings put global "$setting" 0; done
  ;;
install)
  test -s "$apk"
  timeout -k 10s 180s adb install -r "$apk"
  timeout -k 2s 10s adb shell pm path "$STUDENT_TEST_PACKAGE" | grep '^package:'
  ;;
launch)
  activity=$(sed -n "s/^launchable-activity: name='\([^']*\)'.*/\1/p" smoke-results/apk-badging.txt)
  test -n "$activity"
  timeout -k 5s 45s adb shell am start -W -n "$STUDENT_TEST_PACKAGE/$activity" | tee smoke-results/app-launch.txt
  tr -d '\r' < smoke-results/app-launch.txt | grep -Fx 'Status: ok'
  sleep 3
  timeout -k 2s 10s adb shell pidof "$STUDENT_TEST_PACKAGE" | tee smoke-results/app-pid.txt
  test -s smoke-results/app-pid.txt
  ;;
test)
  name=${2:?test required}
  case "$name" in student-settings-smoke|student-rules-smoke|student-home-back-smoke|student-result-layout-smoke) ;; *) exit 2 ;; esac
  if timeout --kill-after=10s 300s /tmp/student-preview-venv/bin/python -u "private-source/.github/scripts/$name.py" 2>&1 | tee "smoke-results/$name.log"; then rc=0; else rc=$?; fi
  printf '%s\t%s\n' "$name" "$rc" >> smoke-results/test-status.tsv
  exit "$rc"
  ;;
collect)
  set +e
  timeout -k 2s 10s adb devices -l > smoke-results/adb-devices.txt 2>&1
  timeout -k 2s 15s adb logcat -d -v threadtime > smoke-results/logcat.txt 2>&1
  timeout -k 2s 15s adb shell dumpsys activity activities > smoke-results/activities.txt 2>&1
  timeout -k 2s 15s adb exec-out screencap -p > smoke-results/final-screen.png 2> smoke-results/screenshot-error.txt
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    { echo '## Preview CI diagnostics'; echo 'Test exit codes (0=pass, 124=timeout; absent=not executed):'; echo '```'; cat smoke-results/test-status.tsv 2>/dev/null; echo '```'; echo 'Emulator results do not constitute physical Fold8 acceptance.'; } >> "$GITHUB_STEP_SUMMARY"
  fi
  exit 0
  ;;
stop)
  timeout -k 2s 10s adb emu kill || true
  if [ -s smoke-results/emulator.pid ]; then kill "$(cat smoke-results/emulator.pid)" 2>/dev/null || true; fi
  ;;
*) echo "Unknown stage: $mode" >&2; exit 2 ;;
esac
printf '%s PASS stage=%s\n' "$(date -u +%FT%TZ)" "$mode"
