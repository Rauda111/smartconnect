#!/bin/sh
# Local viewer only. Does not launch the competition collector.
set -eu
cd "$(dirname "$0")"
if [ -n "${SMARTCONNECT_PYTHON:-}" ]; then
    dashboard_python="$SMARTCONNECT_PYTHON"
elif [ -x .venv/bin/python ]; then
    dashboard_python=.venv/bin/python
elif [ -x /opt/anaconda3/bin/python ]; then
    dashboard_python=/opt/anaconda3/bin/python
else
    dashboard_python=python3
fi
exec "$dashboard_python" -m streamlit run mac_hub/competition/dashboard.py --server.address 127.0.0.1 --browser.gatherUsageStats false
