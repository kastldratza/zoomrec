#!/bin/bash
set -e

# Disable screensaver and power management
xset -dpms &
xset s noblank &
xset s 0 0 &
xset s off &

# Start xfce
/usr/bin/startxfce4 --replace > "$HOME"/xfce.log &
sleep 1
cat "$HOME"/xfce.log