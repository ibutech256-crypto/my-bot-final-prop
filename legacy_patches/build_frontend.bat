@echo off
cd /d C:\prop-frim-bot\frontend
set NEXT_TELEMETRY_DISABLED=1
"C:\Program Files\nodejs\node.exe" node_modules\next\dist\bin\next build > C:\prop-frim-bot\logs\build_out.log 2>&1
echo BUILD_FINISHED >> C:\prop-frim-bot\logs\build_out.log
