# Dorm calendar heartbeat (last_check.json) — STATUS: PAGE LIVE (edits1019, 2026-10-18 20:26 Paris); first heartbeat pushed; routine step must be added to the routine prompt
Every run of the Multi-OTA bed calendar routine (15-min sweep), even with NO change, at the very end:
1. `timeout 20 python3 /workspace/multi-ota/write_heartbeat.py "no change" "<live calendar-version>"` (or "CHANGE: ...").
2. Push ONE file: GitHub push_files owner roycepianist9-debug repo dorm-calendar branch main,
   files [{path: "last_check.json", content: "$file:/workspace/multi-ota/last_check.json"}], message "heartbeat <UTC>".
   Never touch fragments/ or index.html for a heartbeat. If the push fails, log it in runs.log and continue (page then falls back to the publish time, labelled "(last change)").
3. The page (next8 #n8-js) fetches raw.githubusercontent.com/roycepianist9-debug/dorm-calendar/main/last_check.json (then ./last_check.json),
   shows "Last checked HH:MM Paris" / "Dernière vérification : HH:MM Paris", rechecks every 5 min and on tab return. Paris time only.
