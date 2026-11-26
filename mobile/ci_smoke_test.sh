#!/usr/bin/env bash
# Installs the APK on the CI emulator, checks every page loads inside the app,
# and saves screenshots. Run from the repository root.
set -euo pipefail
APP=org.ambesh.community_app
ACTIVITY=$APP/org.beeware.android.MainActivity
OUT=mobile-screenshots
mkdir -p "$OUT"

adb install -r "$(ls dist/*.apk | head -1)"

launch() {  # launch <path>: restart the app on the sample data, open <path>, wait for its server
  adb shell am start -S -W -n "$ACTIVITY" --ez demo true --es path "$1" >/dev/null
  for i in $(seq 1 60); do
    sleep 2
    adb forward tcp:5055 tcp:5055 >/dev/null 2>&1 || true
    if curl -sf -o /dev/null http://127.0.0.1:5055/help; then return 0; fi
  done
  echo "App server did not start"; adb logcat -d | tail -200; return 1
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

adb logcat -d > "$OUT/logcat.txt" || true
if grep -E "Traceback|python.stderr.*Error" "$OUT/logcat.txt" | grep -v "Back button handler" | head -20; then
  echo "Python errors found in the app log (see above)"; exit 1
fi
echo "All checks passed"
