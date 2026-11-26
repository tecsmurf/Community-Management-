#!/usr/bin/env bash
# Installs the APK on the CI emulator, checks every page loads inside the app,
# and saves screenshots. Run from the repository root.
set -euo pipefail
APP=org.ambesh.community_app
ACTIVITY=$APP/org.beeware.android.MainActivity
OUT=mobile-screenshots
mkdir -p "$OUT"

adb install -r "$(ls dist/*.apk | head -1)"
# A freshly booted emulator restarts Google services for a while, and Android
# kills apps that depend on them. Let it settle before starting.
adb shell 'while [ "$(getprop sys.boot_completed)" != 1 ]; do sleep 2; done'
sleep 45

PORT=5055
launch() {  # launch <path>: restart the app on the sample data, open <path>, wait for its server
  adb logcat -d >> "$OUT/logcat.txt" 2>/dev/null || true
  adb logcat -c || true
  adb shell am start -S -W -n "$ACTIVITY" --ez demo true --es path "$1" >/dev/null
  for i in $(seq 1 90); do
    sleep 2
    if [ -z "$(adb shell pidof $APP | tr -d '\r')" ]; then
      echo "App was stopped by the system; starting it again"
      adb shell am start -W -n "$ACTIVITY" --ez demo true --es path "$1" >/dev/null
    fi
    # The app logs the port it serves on (5055 unless that one is busy).
    found=$(adb logcat -d -s python.stdout | sed -n 's/.*serving on port \([0-9]*\).*/\1/p' | tail -1)
    [ -n "$found" ] && PORT=$found
    adb forward tcp:5055 tcp:$PORT >/dev/null 2>&1 || true
    if curl -sf -o /dev/null http://127.0.0.1:5055/help; then return 0; fi
  done
  echo "App server did not start. App and Python lines from the log:"
  adb logcat -d >> "$OUT/logcat.txt" || true
  grep -E "python\.std|AndroidRuntime|MainActivity|FATAL|Traceback|Killing .*community_app|Process .*community_app" "$OUT/logcat.txt" | tail -150
  return 1
}

launch /
echo "App started"
for p in / /members/ /families/ /families/1 /families/1/tree /members/3 /members/new /yuvak-mandal/ \
         "/yuvak-mandal/?tab=alumni" "/yuvak-mandal/?tab=upcoming" /backup /help; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5055$p")
  echo "$p $code"
  [ "$code" = 200 ] || { echo "Page failed: $p"; exit 1; }
done

shot() {  # shot <name> <path>
  launch "$2"
  sleep 6  # let the web view finish drawing
  adb exec-out screencap -p > "$OUT/$1.png"
}
shot 1-home /
shot 2-members /members/
shot 3-family /families/1
shot 4-tree /families/1/tree
shot 5-member /members/3
shot 6-yuvak /yuvak-mandal/
shot 7-add-member "/members/new?family=1"
shot 8-backup /backup

adb logcat -d >> "$OUT/logcat.txt" || true
if grep -E "Traceback|python.stderr.*Error" "$OUT/logcat.txt" | grep -v "Back button handler" | head -20; then
  echo "Python errors found in the app log (see above)"; exit 1
fi
echo "All checks passed"
