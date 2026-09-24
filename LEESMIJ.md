# Carnavalswagen Pi – CV de Zeutekauwn

Raspberry Pi 3B (Debian 13 "trixie", gebruiker `casper`, IP thuis `192.168.68.126`) die op de wagen
muziek afspeelt en de lichtshow stuurt. Bijgewerkt: 23 september 2026.

## Wat draait er op de Pi

| Onderdeel | Wat | Adres / dienst |
|---|---|---|
| Mp3-speler | MPD, crossfade 9 s, muziek in `/var/lib/mopidy/Music` | dienst `mpd` |
| Mp3-webinterface | myMPD | `http://<pi>:8081`, dienst `mympd` |
| Spotify | Raspotify, speakernaam **CV de Zeutekauwn** | dienst `raspotify` |
| Lichtsturing | Zeutekauwn DMXDesk (`/home/casper/dmxdesk/`) | telefoon: `http://<pi>:8080`, instellingen: `http://<pi>:8080/instellingen`, dienst `zeutekauwn-dmx` |
| Beat-analyse Spotify | `beatluister.py spotify` (zit in de raspotify-dienst) | – |
| Beat-analyse mp3 | `beatluister.py mpd` | dienst `zeutekauwn-beat-mpd` |

## Hoe het geluid loopt

- **Mp3:** MPD → koptelefoonuitgang (`hw:1,0`) + een aftakking `/var/lib/mpd/beat.fifo` → beatluister → DMXDesk
- **Spotify:** librespot (pipe) → beatluister → `aplay` → koptelefoonuitgang, en beats → DMXDesk
- Spotify en MPD spelen om de beurt. Start Spotify, dan stopt MPD vanzelf (`spotify-event.sh`).
  Terug naar mp3: Spotify op pauze, dan play in myMPD.
- Beats gaan via UDP `127.0.0.1:8091` naar DMXDesk.

## Wat de Pi uit de muziek haalt (beatluister.py)

- **BPM en maat**, met aubio. Snelle nummers (bv. 208) worden via de kick-drum herkend en verdubbeld.
- **Melodie**: de sterkste toon tussen 220 en 2000 Hz. Elke toon heeft een eigen kleur (kleurmodus "♪ Melodie").
- **Energie**: rustig ↔ extreem, uit luidheid (t.o.v. de laatste 30 s), drukte en helderheid.
  "Show volgt energie" maakt bewegingen en wissels trager en kleiner, of juist sneller en groter.
- **Drops**: na een rustig stuk barst het los → korte witte flits.
- IJkwaarden staan bovenaan `beatluister.py` (IJK_DRUKTE, IJK_HOOG), afgestemd op de 9 nummers van sept 2026.

## Inhoud van deze map

- `dmxdesk/`: de lichtsturing. `dmxdesk.py`, `beatluister.py`, `web/telefoon.html`, `web/instellingen.html`
- `pi-config/`: kopieën van de instellingen op de Pi
  - `mpd.conf` → `/etc/mpd.conf`
  - `raspotify-conf` → `/etc/raspotify/conf`
  - `raspotify-beat.conf` → `/etc/systemd/system/raspotify.service.d/beat.conf`
  - `zeutekauwn-dmx.service`, `zeutekauwn-beat-mpd.service` → `/etc/systemd/system/`
  - `spotify-event.sh` → `/usr/local/bin/spotify-event.sh`
  - `show.json` → `/home/casper/dmxdesk/show.json` (fixtures, profielen, scènes, show-instellingen)
- `oud-script/`: het oude `dmx_control.py` (V10.21) met zijn config, alleen ter referentie

## Alles terugzetten op een nieuwe SD-kaart

1. Raspberry Pi OS (Debian 13, 64-bit) installeren, gebruiker `casper`, wifi instellen.
2. Pakketten:
   `sudo apt install mpd mpc python3-serial python3-aubio alsa-utils`
3. Raspotify: repo-sleutel en repo toevoegen zoals op https://github.com/dtcooper/raspotify,
   dan `sudo apt install raspotify`. (Het officiële installatiescript kan struikelen over Debian 13.)
4. myMPD: repo `https://download.opensuse.org/repositories/home:/jcorporation/Debian_13/`,
   dan `sudo apt install mympd`. Poort 8081 instellen in `/var/lib/mympd/config/http_port`.
5. Bestanden uit `pi-config/` en `dmxdesk/` terugzetten op de plekken hierboven.
   `beatluister.py` moet ook naar `/usr/local/lib/zeutekauwn/beatluister.py`
   (raspotify mag niet in `/home` kijken).
6. `sudo systemctl daemon-reload`, en dan
   `sudo systemctl enable --now mpd mympd raspotify zeutekauwn-dmx zeutekauwn-beat-mpd`
7. `sudo systemctl disable --now mopidy` (als Mopidy er nog op staat)

## Uitzetten

Nooit zomaar de stekker eruit trekken: de SD-kaart kan beschadigen. Gebruik op de instellingenpagina
(Show-tabblad, blok "Raspberry Pi") de knop **⏻ Pi uitzetten** en wacht tot het groene lampje niet meer
knippert (~20 s). Via SSH kan het ook: `sudo shutdown now`. Weer aanzetten = stekker erin; alles start vanzelf.

## Bekende valkuilen

- **ALSA dmix werkt niet** op de koptelefoonuitgang van de Pi (het afspelen blijft hangen). Daarom spelen ze om de beurt.
- **Spotify-geluid via de pijp:** alleen hele samples (4 bytes) doorgeven, anders krijg je harde ruis na een pauze. Dit zit al in `beatluister.py`.
- **Spotify zachter dan mp3:** volume-normalisatie staat daarom uit, startvolume 100, volumeregeling lineair.
- Poort 8080 = DMXDesk, 8081 = myMPD, 6600 = MPD, 8091 = beats (alleen intern).

## Nog te doen

- Testen met de USB-DMX-dongle en de echte lampen.
- De schuiven "Licht gelijk zetten met de muziek" kalibreren (Spotify en mp3).
- Echte profielen maken zodra bekend is welke pars, moving heads en rookmachine het worden.
  De profielen "uit oud script" zijn gokwerk.
