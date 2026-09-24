#!/bin/sh
# DMXDesk op een Raspberry Pi installeren of bijwerken (als dienst, start vanzelf bij het aanzetten).
# Uitvoeren in de map van DMXDesk:   sh pi/installeren.sh
# Daarna: telefoon op http://<ip-van-de-pi>:8080/  en het volledige paneel op http://<ip-van-de-pi>:8080/desk
set -e
MAP=$(cd "$(dirname "$0")/.." && pwd)
GEBRUIKER=$(id -un)
echo "DMXDesk in $MAP (gebruiker $GEBRUIKER)"

sudo apt-get install -y python3-numpy python3-serial python3-qrcode python3-mido python3-rtmidi python3-aubio alsa-utils

# dienst: paden en gebruiker invullen
sed -e "s#/home/casper/dmxdesk#$MAP#g" -e "s#=casper#=$GEBRUIKER#g" "$MAP/pi/zeutekauwn-dmx.service" \
  | sudo tee /etc/systemd/system/zeutekauwn-dmx.service > /dev/null

# beat-luisteraar (voor Spotify/MPD op de Pi) buiten /home, want raspotify mag daar niet kijken
sudo install -D -m 644 "$MAP/dmxdesk/beatluister.py" /usr/local/lib/zeutekauwn/beatluister.py

# de knop 'Uitzetten' in de app mag de Pi netjes afsluiten, zonder wachtwoord
echo "$GEBRUIKER ALL=(root) NOPASSWD: /usr/bin/systemctl poweroff, /usr/bin/systemctl reboot" \
  | sudo tee /etc/sudoers.d/dmxdesk > /dev/null
sudo chmod 440 /etc/sudoers.d/dmxdesk

# Spotify (raspotify): geluid via de beat-luisteraar, met 4 s voorsprong voor het licht
if [ -d /etc/raspotify ]; then
  sudo install -D -m 644 "$MAP/pi/raspotify-beat.conf" /etc/systemd/system/raspotify.service.d/beat.conf
fi

sudo systemctl daemon-reload
sudo systemctl enable zeutekauwn-dmx
sudo systemctl restart zeutekauwn-dmx
for dienst in raspotify zeutekauwn-beat-mpd; do
  if systemctl list-unit-files "$dienst.service" > /dev/null 2>&1 && systemctl is-enabled --quiet "$dienst" 2>/dev/null; then
    sudo systemctl restart "$dienst"
  fi
done
IP=$(hostname -I | awk '{print $1}')
echo
echo "Klaar. Telefoon: http://$IP:8080/   Bedieningspaneel: http://$IP:8080/desk"
