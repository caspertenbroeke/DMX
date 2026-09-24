#!/bin/sh
# Wordt door raspotify aangeroepen bij elke Spotify-gebeurtenis.
# Als Spotify gaat spelen: stop MPD zodat Spotify de geluidskaart krijgt.
case "$PLAYER_EVENT" in
  playing|started)
    /usr/bin/mpc -q -h localhost stop || true
    ;;
esac
