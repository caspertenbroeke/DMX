# DMXDesk

Lichtsturing voor pars, moving heads, LED-bars, lasers en rook, op de beat van de muziek.
Een echte app voor **Windows, macOS en Linux**, en hij draait ook als dienst op een **Raspberry Pi**.
Bediening in het app-venster, of vanaf je **telefoon of tablet** via wifi.

Begonnen als lichtsturing van de carnavalswagen van CV de Zeutekauwn; nu voor iedereen te gebruiken.

## Wat kan het

| | |
|---|---|
| **Live** | Podium met live licht, scènes (sneltoetsen 1–0), cuelijsten, faders, STROBE / SMOKE / BLINDER vasthouden, tempo ½× – 4×, freeze, blackout |
| **Effecten** | 10 kleur-, 21 intensiteits- en 13 bewegingseffecten, allemaal op de beat. Palet, snelheid, spreiding, auto-show. **Lagen**: elke groep (pars, moving heads, LED-bars, …) eigen patroon, snelheid en kleur |
| **Lichtman** | De show volgt het nummer zoals een lichtman: rustig nummer = rustig licht (ook op 150 BPM), opbouw = steeds sneller en naar wit, vlak voor de drop even donker, drop = flits en vol gas met een knal op elke kick. Luistert vooral naar de kick, niet alleen naar het tempo |
| **Programmer** | Lampen aanklikken en met de hand instellen: dimmer, kleur, pan/tilt (XY-veld), en elk kanaal met knoppen voor alle functies uit de handleiding (gobo, kleurwiel, laserpatroon, …). Opslaan als scène of als look |
| **Laser & patronen** | Patroon, patroongroep, kleurprogramma, zoom, draaien, kantelen, golf, tekenen, ingebouwde effecten, prisma, focus, … laten wisselen op de beat, willekeurig, of meegaan met de energie van de muziek |
| **Scènes** | Vaste looks en/of effecten, met overvloeien (fade). Cuelijsten die in beats of seconden door scènes lopen |
| **Podium** | Plattegrond: sleep lampen naar hun plek. Links→rechts bepaalt hoe chases en golven lopen |
| **Patch** | Lampen toevoegen uit de bibliotheek, universes en adressen, overlap-controle, DIP-schakelaar-hulp |
| **Bibliotheek** | 660 lampen: generieke profielen + de complete [Open Fixture Library](https://open-fixture-library.org) (644 lampen van 134 merken, werkt offline). Zelf inlezen: QLC+ (`.qxf`) en OFL (`.json`) |
| **Uitgangen** | USB-DMX (FTDI / Enttec Open DMX), Enttec DMX USB Pro, Art-Net, sACN (E1.31). Meerdere universes |
| **Spotify-speaker** | DMXDesk verschijnt in Spotify als speaker (zoals Sonos). De muziek wordt eerst geanalyseerd en 8 s later afgespeeld, zodat het licht vooruit weet waar de beats en drops vallen. Met een eigen **speler** (vorige / pauze / volgende / volume) in de app en op je telefoon; die werken meteen |
| **Geluid** | Luistert mee via microfoon, line-in of het geluid van de computer zelf: BPM, beat, melodie (kleuren per toon), energie en drops. Op de Pi via Spotify/MPD |
| **Monitor** | Alle 512 kanalen per universe, live |
| **Bediening** | Telefoonpagina met grote knoppen, pincode, MIDI-controllers (leren), sneltoetsen, QR-code om je telefoon te koppelen |

## Downloaden en installeren

De apps worden automatisch gebouwd door GitHub (zie *Nieuwe versie uitbrengen*). Download bij
**Releases** (of bij een build onder *Actions → Artifacts*):

- **Windows:** `DMXDesk-…-windows-installer.exe` (installeren, met snelkoppeling) of de `.zip` (uitpakken, `DMXDesk.exe` starten).
  Windows zegt de eerste keer misschien *"Windows heeft uw pc beschermd"*: klik **Meer info → Toch uitvoeren**
  (de app is niet betaald-ondertekend). Sta netwerktoegang toe als Windows daarom vraagt (voor DMXDesk én voor
  **dmxdesk-spotify**, dat is de Spotify-speaker; kies *Privénetwerken*).
- **macOS:** `DMXDesk-…-macos-apple-silicon.dmg` (M1/M2/M3/M4) of `…-macos-intel.dmg`. Sleep DMXDesk naar Programma's.
  De eerste keer: **rechtsklik → Open**, of *Systeeminstellingen → Privacy en beveiliging → Toch openen*.
  Sta de microfoon toe als je DMXDesk naar de muziek wilt laten luisteren, en *apparaten in het lokale netwerk*
  (nodig voor de Spotify-speaker, Art-Net/sACN en je telefoon).
- **Linux:** `DMXDesk-…-linux-x64.tar.gz` uitpakken en `DMXDesk/DMXDesk` starten (opent in je browser).
  Voor de geluidskaart en de Spotify-speaker: `sudo apt install libportaudio2`.
- **Zelf vanuit de broncode** (elk systeem met Python 3.9+):
  ```
  pip install ".[app]"
  dmxdesk            # of: python -m dmxdesk
  ```

De show wordt automatisch bewaard (Windows: `%APPDATA%\DMXDesk`, macOS: `~/Library/Application Support/DMXDesk`,
Linux: `~/.config/dmxdesk`). Via *Instellingen → Show exporteren* maak je een bestand om te bewaren of te delen.

### Opties bij het starten

```
dmxdesk                  app-venster (of de browser als dat niet lukt)
dmxdesk --browser        altijd in de gewone browser
dmxdesk --server         zonder scherm (Raspberry Pi / dienst)
dmxdesk --poort 8090     andere poort (standaard 8080)
dmxdesk --show pad.json  ander showbestand
```

## De eerste keer

1. **Uitgangen:** sluit je USB-DMX-kabel aan (staat al klaar op *Automatisch zoeken*), of voeg Art-Net/sACN toe.
   Het groene bolletje bovenin = DMX gaat de deur uit.
2. **Patch → + Lamp toevoegen:** zoek je lamp op merk/model, kies de DMX-modus die op de lamp staat, het aantal
   en de universe. DMXDesk zoekt zelf een vrij adres. Zet dat adres ook op de lamp (display of DIP-schakelaars).
3. **Podium:** sleep de lampen naar hun plek.
4. **Geluid:** kies je microfoon of line-in en zet *Luisteren* aan. Of tik het tempo met de spatiebalk.
5. **Effecten / Programmer:** maak een mooie look en sla hem op als **scène**. Scènes staan op *Live*.

### Doet een lamp niets?

1. **Adres:** het adres op de lamp (display of DIP-schakelaars) moet hetzelfde zijn als in Patch. Met de knop
   **Zoek** in Patch knippert de lamp op dat adres.
2. **DMX-modus:** zet de lamp in de DMX-modus met precies zoveel kanalen als het profiel (niet in auto- of geluidsmodus).
3. **Kabel:** bovenin moet **DMX ok** groen staan. Kies bij Uitgangen "USB-DMX-kabel (herkent zelf het type)":
   DMXDesk vraagt de kabel dan zelf of hij een Enttec Pro(-kloon) of een simpele Open DMX-kabel is.
4. In de **Monitor** zie je welke waarden er echt naar buiten gaan; in de **Programmer** zet je elk kanaal met de hand.

### Een lamp uit de handleiding toevoegen

Staat je lamp niet in de bibliotheek, maak dan in **Profielen** een profiel: per kanaal de **functie** (dimmer, rood,
patroon, draaien, ingebouwd programma, …) en onder **Opties** de bereiken uit de handleiding, één per regel, bijvoorbeeld
`125-149 Animaties 1`. Die keuzes verschijnen dan als knoppen in de Programmer, en de show kan ermee wisselen op de beat.
Een QLC+-bestand (.qxf) of Open Fixture Library-bestand (.json) van je lamp kun je ook direct importeren.

### Telefoon of tablet

Zet je telefoon op hetzelfde wifi-netwerk en open het adres van *Instellingen → Telefoon verbinden*
(of scan de QR-code). Daar staan de grote knoppen SMOKE, STROBE, SMOKE + STROBE, BLINDER en BLACKOUT,
en je scènes. Via "alles →" kom je bij het volledige paneel. Met een **pincode** kan alleen wie de code weet meebedienen.

### Sneltoetsen

Spatie = tap · B = blackout · F = freeze · A = auto-show · S / R / W (vasthouden) = strobe / rook / blinder ·
1 … 9, 0 = scène 1–10 · Esc = scène loslaten · ← / → = vorige / volgende cue

### MIDI-controller

*Instellingen → MIDI-controller*: kies je controller, kies een actie (scène, fader, strobe vasthouden, …), klik
**Leren** en druk op de knop of beweeg de fader. Werkt met o.a. APC mini, Launchpad, nanoKONTROL.

## Spotify-speaker en speler

De app is meteen een Spotify-speaker, net als een Sonos of de Pi met raspotify:

1. Start DMXDesk (computer en telefoon op hetzelfde wifi-netwerk).
2. Open Spotify, tik op het speaker-icoon (*Apparaten*) en kies **DMXDesk**.
3. De muziek komt uit de luidsprekers van de computer, en het licht loopt mee.

DMXDesk hoort elk stukje muziek eerst en speelt het pas **8 seconden later** af (instelbaar 0–20 s). Zo weet de
lichtman vooraf waar de beats, de melodie en de drops vallen. Pauze, volgend nummer, spoelen en volume werken
toch meteen: de speaker meldt ze direct, DMXDesk gooit dan de wachtrij weg of zet hem stil, en past het volume pas
bij het afspelen toe.

**De speler** zit onderin de app (hoes, titel, vorige / pauze / volgende, voortgang, volume) en op de telefoonpagina
(tabblad **Muziek**). Hij bedient dezelfde Spotify-sessie: wat je in de Spotify-app doet, zie je in DMXDesk en
andersom.

In *Geluid → Spotify-speaker* stel je in: aan/uit, de naam in Spotify, via welke luidspreker/geluidskaart hij
speelt, en hoe ver het licht vooruit hoort. Loopt het licht nog net voor of achter? Gebruik de schuif
*Spotify-speaker* bij *Licht gelijk zetten met de muziek*.

- Spotify **Premium** is nodig; dat geldt voor elke Spotify-speaker.
- Verschijnt hij niet in Spotify? Kijk of Windows/macOS de netwerktoegang heeft toegestaan (zie *Downloaden en
  installeren*) en of computer en telefoon op hetzelfde netwerk zitten (gastnetwerken blokkeren dit vaak).
- De speaker is een eigen klein programma (`spotify-speaker/`, Rust) gebouwd met
  [librespot](https://github.com/librespot-org/librespot) (MIT-licentie); hij zit in de app. Vanuit de broncode:
  `cd spotify-speaker && cargo build --release`, of wijs hem aan met `DMXDESK_SPEAKER=pad`.
- Op de Pi (`--server`) staat hij standaard uit: daar doet raspotify dit (zie hieronder).

## De lichtman

*Effecten → Lichtman* (standaard aan). De show kijkt niet alleen naar het tempo, maar vooral naar **de kick**:
pompt de bas op elke tel (dance, hardstyle) of niet (rustig nummer, opbouw, breakdown). Daaruit volgt waar het
nummer is:

| Stuk | Wat het licht doet |
|---|---|
| **Rustig** | Gedimd, zachte overgangen, effecten 4× trager, kleuren wisselen per 2 maten, langzame golf over de lampen |
| **Break** | Idem, na een stuk met kick (breakdown): klaar voor de volgende klap. Het tempo blijft staan |
| **Opbouw** | Op de maat steeds sneller knipperen (1, 2, 4, 8 keer per tel), feller en naar wit; vlak voor de drop even donker |
| **Drop** | Witte flits precies op de eerste kick, dan vol gas: effecten op de beat, knal op elke kick, snel en groot |
| **Groove** | Kick, maar niet heel hard: op de maat, effecten 2× trager |

De drop is het moment dat de kick terugkomt na een stuk zonder kick. Met de Spotify-speaker ziet de lichtman die tot
8 s van tevoren aankomen; via de microfoon/line-in herkent hij alles ook, alleen iets later en zonder opbouw vooraf.
**Rustig ↔ wild** bepaalt hoe groot het verschil tussen de stukken is. Met *Auto-show* kiest hij ook zelf
passende patronen en bij een drop meteen iets nieuws.

## Lagen

*Effecten → Laag*: kies een groep (zoals ingesteld in de Patch) en zet **Eigen patronen** aan. Die laag krijgt dan
eigen kleur, intensiteit en beweging, bijvoorbeeld de pars een chase en de moving heads een cirkel; een chase loopt
dan binnen de laag. De lichtman, master en scènes werken gewoon op alle lagen; een scène bewaart ook de lagen.

## Raspberry Pi (carnavalswagen CV de Zeutekauwn)

Raspberry Pi 3B (Debian 13 "trixie", gebruiker `casper`, IP thuis `192.168.68.126`) die op de wagen
muziek afspeelt en de lichtshow stuurt.

### Wat draait er op de Pi

| Onderdeel | Wat | Adres / dienst |
|---|---|---|
| Mp3-speler | MPD, crossfade 9 s, muziek in `/var/lib/mopidy/Music` | dienst `mpd` |
| Mp3-webinterface | myMPD | `http://<pi>:8081`, dienst `mympd` |
| Spotify | Raspotify, speakernaam **CV de Zeutekauwn** | dienst `raspotify` |
| Lichtsturing | DMXDesk (`/home/casper/dmxdesk/`) | telefoon: `http://<pi>:8080`, paneel: `http://<pi>:8080/desk`, dienst `zeutekauwn-dmx` |
| Beat-analyse Spotify | `beatluister.py spotify --voorsprong 4` (zit in de raspotify-dienst); de lichtman werkt ook op de Pi | – |
| Beat-analyse mp3 | `beatluister.py mpd` | dienst `zeutekauwn-beat-mpd` |

### Van DMXDesk 1 naar 2 (bijwerken)

De show (`show.json`) wordt automatisch omgezet; de lampen doen precies hetzelfde als in versie 1 (dat wordt getest).

```
sudo systemctl stop zeutekauwn-dmx
cd /home/casper
mv dmxdesk dmxdesk-v1                                   # oude versie bewaren
git clone https://github.com/caspertenbroeke/DMX.git dmxdesk   # (of de zip downloaden en uitpakken)
cp dmxdesk-v1/show.json dmxdesk/show.json
cd dmxdesk && sh pi/installeren.sh
```

Later bijwerken: `cd /home/casper/dmxdesk && git pull && sh pi/installeren.sh`.

### Hoe het geluid loopt

- **Mp3:** MPD → koptelefoonuitgang (`hw:1,0`) + een aftakking `/var/lib/mpd/beat.fifo` → beatluister → DMXDesk
- **Spotify:** librespot (pipe) → beatluister (analyseert meteen) → 4 s later `aplay` → koptelefoonuitgang, en de
  beats, noten, energie en drops → DMXDesk, met het moment waarop ze te horen zijn. Het licht weet dus 4 s vooruit
  wat er komt. `sh pi/installeren.sh` zet dit klaar (`/etc/systemd/system/raspotify.service.d/beat.conf`).
  Terug naar geen voorsprong: haal `--voorsprong 4` weg uit dat bestand en `sudo systemctl daemon-reload && sudo systemctl restart raspotify`.
- **Mp3 met voorsprong (optioneel):** vervang in `/etc/mpd.conf` het blok `audio_output` "Headphones" én het
  blok "Beat-analyse" door

  ```
  audio_output {
      type        "pipe"
      name        "Headphones (met voorsprong)"
      command     "/usr/bin/python3 -u /usr/local/lib/zeutekauwn/beatluister.py pijp mpd --voorsprong 4"
      format      "44100:16:2"
      mixer_type  "software"
  }
  ```

  en zet de dienst `zeutekauwn-beat-mpd` uit (`sudo systemctl disable --now zeutekauwn-beat-mpd`). Zet daarna de
  schuif *Mp3/MPD (Pi)* op ongeveer 200 ms, net als Spotify.
- Spotify en MPD spelen om de beurt. Start Spotify, dan stopt MPD vanzelf (`spotify-event.sh`).
  Terug naar mp3: Spotify op pauze, dan play in myMPD.
- Beats gaan via UDP `127.0.0.1:8091` naar DMXDesk.

### Wat de Pi uit de muziek haalt (beatluister.py)

- **BPM en maat**, met aubio (op de Pi; op andere computers een eigen beat-zoeker met alleen numpy).
  Snelle nummers (bv. 208) worden via de kick-drum herkend en verdubbeld.
- **Melodie**: de sterkste toon tussen 220 en 2000 Hz. Elke toon heeft een eigen kleur (kleurmodus "♪ Melodie").
- **Energie**: rustig ↔ extreem, uit luidheid (t.o.v. de laatste 30 s), drukte en helderheid.
  "Show volgt energie" maakt bewegingen en wissels trager en kleiner, of juist sneller en groter.
- **Drops**: na een rustig stuk barst het los → korte witte flits. Met voorsprong: eerst een opbouw ernaartoe.
- IJkwaarden staan bovenaan `dmxdesk/beatluister.py` (IJK_DRUKTE, IJK_HOOG), afgestemd op de 9 nummers van sept 2026.

### Alles terugzetten op een nieuwe SD-kaart

1. Raspberry Pi OS (Debian 13, 64-bit) installeren, gebruiker `casper`, wifi instellen.
2. Pakketten: `sudo apt install git mpd mpc python3-serial python3-aubio alsa-utils`
3. Raspotify: repo-sleutel en repo toevoegen zoals op https://github.com/dtcooper/raspotify,
   dan `sudo apt install raspotify`. (Het officiële installatiescript kan struikelen over Debian 13.)
4. myMPD: repo `https://download.opensuse.org/repositories/home:/jcorporation/Debian_13/`,
   dan `sudo apt install mympd`. Poort 8081 instellen in `/var/lib/mympd/config/http_port`.
5. DMXDesk: `git clone … /home/casper/dmxdesk`, `cp dmxdesk/pi/show.json dmxdesk/show.json`, `sh pi/installeren.sh`.
6. De rest van `pi/` terugzetten:
   - `mpd.conf` → `/etc/mpd.conf`
   - `raspotify-conf` → `/etc/raspotify/conf`
   - `raspotify-beat.conf` → `/etc/systemd/system/raspotify.service.d/beat.conf`
   - `zeutekauwn-beat-mpd.service` → `/etc/systemd/system/`
   - `spotify-event.sh` → `/usr/local/bin/spotify-event.sh`
7. `sudo systemctl daemon-reload`, en dan `sudo systemctl enable --now mpd mympd raspotify zeutekauwn-beat-mpd`
8. `sudo systemctl disable --now mopidy` (als Mopidy er nog op staat)

### Uitzetten

Nooit zomaar de stekker eruit trekken: de SD-kaart kan beschadigen. Gebruik *Instellingen → Systeem →
⏻ Uitzetten* en wacht tot het groene lampje niet meer knippert (~20 s). Via SSH kan het ook: `sudo shutdown now`.
Weer aanzetten = stekker erin; alles start vanzelf.

### Bekende valkuilen

- **ALSA dmix werkt niet** op de koptelefoonuitgang van de Pi (het afspelen blijft hangen). Daarom spelen ze om de beurt.
- **Spotify-geluid via de pijp:** alleen hele samples (4 bytes) doorgeven, anders krijg je harde ruis na een pauze. Dit zit al in `beatluister.py`.
- **Spotify zachter dan mp3:** volume-normalisatie staat daarom uit, startvolume 100, volumeregeling lineair.
- Poort 8080 = DMXDesk, 8081 = myMPD, 6600 = MPD, 8091 = beats (alleen intern).

## Nieuwe versie uitbrengen

1. Versienummer ophogen in `dmxdesk/__init__.py` en `pyproject.toml`.
2. Committen, en een tag pushen: `git tag v2.0.1 && git push origin v2.0.1`.
3. GitHub bouwt dan de Windows-installer, de Mac-apps en de Linux-versie en zet ze bij **Releases**.

Bij elke gewone push draaien de tests en worden de apps ook gebouwd (te downloaden onder *Actions → Artifacts*).

## Voor ontwikkelaars

```
dmxdesk/
  app.py          starten: venster (pywebview) / browser / --server
  engine.py       de motor: lagen (effecten → scène → programmer → master → vasthouden), 40 frames/s
  effecten.py     alle kleur-, intensiteits- en bewegingseffecten
  profielen.py    kanaalfuncties en ingebouwde profielen
  bibliotheek.py  Open Fixture Library en QLC+ (.qxf) inlezen
  uitvoer.py      USB-DMX, Enttec Pro, Art-Net, sACN
  audio.py        geluidskaart → beatluister.Analyse
  spotify.py      Spotify-speaker en speler: dmxdesk-spotify → beatluister.Doorgever (analyseren, later afspelen)
  lichtman.py     secties van het nummer (rustig/break/opbouw/groove/drop) en hoe de show zich dan gedraagt
  beatluister.py  beat, BPM, melodie, energie, drops (ook los te gebruiken op de Pi)
  midi.py         MIDI-controllers
  server.py       webserver + JSON-API + live-stream (Server-Sent Events)
  web/            bedieningspaneel (index.html + js/) en telefoonpagina
  data/ofl.json.gz  de ingepakte Open Fixture Library
spotify-speaker/  de Spotify-speaker (Rust, op librespot): audio + gebeurtenissen naar DMXDesk, commando's terug
packaging/        PyInstaller-recept, icoon, Windows-installer
pi/               instellingen en diensten voor de Raspberry Pi
tests/            python -m pytest
tools/ofl_bijwerken.py   Open Fixture Library opnieuw ophalen
oud/dmxdesk_v1.py        versie 1, alleen om te testen dat versie 2 hetzelfde licht geeft
```

Testen: `pip install numpy pyserial pytest && python -m pytest`.
App zelf bouwen: `pip install -r packaging/requirements-app.txt pyinstaller pillow && python packaging/bouw.py`
(met de Spotify-speaker erin: eerst `cd spotify-speaker && cargo build --release --locked`, Rust 1.85 of nieuwer).

## Nog te doen

- Testen met de USB-DMX-dongle en de echte lampen.
- De schuiven "Licht gelijk zetten met de muziek" kalibreren (Spotify-speaker, Spotify op de Pi, mp3 en geluidskaart).
- Echte profielen kiezen zodra bekend is welke pars, moving heads en rookmachine het worden (nu kan dat uit de bibliotheek).
