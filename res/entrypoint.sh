#!/bin/bash
set -e
if [[ "$DEBUG" == "True" ]]; then
  set -x
fi

cleanup () {
    kill -s SIGTERM $!
    exit 0
}
trap cleanup SIGINT SIGTERM

VNC_IP=$(hostname -i)

# Change vnc password
mkdir -p "$HOME/.vnc"
PASSWD_PATH="$HOME/.vnc/passwd"

if [[ -f $PASSWD_PATH ]]; then
    rm -f "$PASSWD_PATH"
fi

echo "$VNC_PW" | vncpasswd -f >> "$PASSWD_PATH"
chmod 600 "$PASSWD_PATH"

# Remove old vnc locks
vncserver -kill "$DISPLAY" &> "$START_DIR"/vnc_startup.log || rm -rf /tmp/.X*-lock /tmp/.X11-unix &> "$START_DIR"/vnc_startup.log

echo -e "\nDISPLAY = $DISPLAY\nVNC_COL_DEPTH = $VNC_COL_DEPTH\nVNC_RESOLUTION = $VNC_RESOLUTION\nVNC_IP = $VNC_IP\nVNC_PORT = $VNC_PORT"
vncserver "$DISPLAY" -depth "$VNC_COL_DEPTH" -geometry "$VNC_RESOLUTION" &> "$START_DIR"/vnc_startup.log

echo -e "\nConnect to $VNC_IP:$VNC_PORT"

# Start xfce4
"$START_DIR"/xfce.sh &> "$START_DIR"/xfce.log

# Cleanup to ensure pulseaudio is stateless
rm -rf /var/run/pulse /var/lib/pulse

# Start audio
pulseaudio -D -vvv --exit-idle-time=-1 --log-level=error

echo -e "\nStart script.."
sleep 5

# Start python script in separated terminal
if [[ "$DEBUG" == "True" ]]; then
  # Wait if something failed
  python3 -u "${HOME}"/zoomrec.py || set +x && echo "Zoomrec failed! wait ..." && while true; do sleep 10; done
else
  # Exit container if something failed
  python3 -u "${HOME}"/zoomrec.py
fi