sudo pigpiod
/usr/bin/screen -S panel_screen -dmL -L -Logfile ~/panel_screen_log.log ~/.local/bin/panel serve ~/PowerPi/panel.py --allow-websocket-origin=* --autoreload --port=8080
