//! Spotify Connect-speaker voor DMXDesk, gebouwd op librespot.
//!
//! In de Spotify-app kies je deze speaker (zoals een Sonos). Het geluid gaat niet zelf naar de
//! luidspreker maar naar DMXDesk, dat het eerst analyseert (beat, kick, drops) en daarna afspeelt.
//!
//! Stdout: een reeks berichten, elk `[soort: 1 byte][lengte: u32 little-endian][inhoud]`:
//!   `A` audio (16 bit stereo, 44,1 kHz)     `S` audio begint      `P` audio stopt (pauze/stop)
//!   `E` gebeurtenis (JSON): nummer, volume, pauze, spoelen, ...
//! Audio en S/P komen uit dezelfde draad, dus precies in de goede volgorde.
//!
//! Stdin: één commando per regel: `play`, `pause`, `playpause`, `next`, `prev`, `volume <0-100>`,
//! `seek <ms>`, `shuffle <0|1>`, `repeat <0|1>`. Gaat stdin dicht (DMXDesk is weg), dan stopt deze speaker ook.
//!
//! Het volume wordt hier níet op het geluid toegepast: DMXDesk doet dat pas bij het afspelen. Zo hoort de
//! analyse altijd het volle signaal en werkt de volumeknop meteen (ook met seconden voorsprong).

use std::io::{self, Write};
use std::sync::Arc;
use std::sync::atomic::{AtomicU16, Ordering};
use std::time::{Duration, Instant};

use futures_util::StreamExt;
use librespot_connect::{ConnectConfig, Spirc};
use librespot_core::{
    Error,
    authentication::Credentials,
    cache::Cache,
    config::{DeviceType, SessionConfig},
    session::Session,
};
use librespot_discovery::Discovery;
use librespot_metadata::audio::UniqueFields;
use librespot_playback::{
    audio_backend::{Sink, SinkResult},
    config::{Bitrate, PlayerConfig},
    convert::Converter,
    decoder::AudioPacket,
    mixer::{Mixer, MixerConfig},
    player::{Player, PlayerEvent},
};
use serde_json::{Value, json};
use sha1::{Digest, Sha1};
use tokio::io::{AsyncBufReadExt, BufReader};

// ---------------------------------------------------------------- berichten naar DMXDesk

fn bericht(soort: u8, inhoud: &[u8]) {
    let mut uit = io::stdout().lock();
    let ok = uit.write_all(&[soort]).is_ok()
        && uit.write_all(&(inhoud.len() as u32).to_le_bytes()).is_ok()
        && uit.write_all(inhoud).is_ok()
        && uit.flush().is_ok();
    if !ok {
        std::process::exit(0); // DMXDesk luistert niet meer
    }
}

fn gebeurtenis(v: Value) {
    bericht(b'E', v.to_string().as_bytes());
}

/// Audio-uitgang: alles gaat (in volgorde) naar DMXDesk.
struct DmxSink;

impl Sink for DmxSink {
    fn start(&mut self) -> SinkResult<()> {
        bericht(b'S', &[]);
        Ok(())
    }

    fn stop(&mut self) -> SinkResult<()> {
        bericht(b'P', &[]);
        Ok(())
    }

    fn write(&mut self, packet: AudioPacket, converter: &mut Converter) -> SinkResult<()> {
        if let AudioPacket::Samples(samples) = packet {
            let s16 = converter.f64_to_s16(&samples);
            let mut bytes = Vec::with_capacity(s16.len() * 2);
            for s in s16 {
                bytes.extend_from_slice(&s.to_le_bytes());
            }
            bericht(b'A', &bytes);
        }
        Ok(())
    }
}

/// Mixer die alleen het volume onthoudt (DMXDesk past het toe bij het afspelen).
struct DmxMixer(AtomicU16);

impl Mixer for DmxMixer {
    fn open(_: MixerConfig) -> Result<Self, Error> {
        Ok(DmxMixer(AtomicU16::new(u16::MAX / 2)))
    }

    fn volume(&self) -> u16 {
        self.0.load(Ordering::Relaxed)
    }

    fn set_volume(&self, volume: u16) {
        self.0.store(volume, Ordering::Relaxed)
    }
}

fn procent(volume: u16) -> u32 {
    (volume as u32 * 100 + 32767) / 65535
}

fn gebeurtenis_van(e: PlayerEvent) -> Option<Value> {
    use PlayerEvent::*;
    Some(match e {
        Loading { play_request_id, track_id, position_ms } => {
            json!({"t": "laden", "verzoek": play_request_id, "id": track_id.to_string(), "pos": position_ms})
        }
        Playing { play_request_id, track_id, position_ms } => {
            json!({"t": "speelt", "verzoek": play_request_id, "id": track_id.to_string(), "pos": position_ms})
        }
        Paused { play_request_id, track_id, position_ms } => {
            json!({"t": "pauze", "verzoek": play_request_id, "id": track_id.to_string(), "pos": position_ms})
        }
        Seeked { play_request_id, position_ms, .. } => {
            json!({"t": "gespoeld", "verzoek": play_request_id, "pos": position_ms})
        }
        EndOfTrack { play_request_id, .. } => json!({"t": "einde", "verzoek": play_request_id}),
        Stopped { play_request_id, .. } => json!({"t": "gestopt", "verzoek": play_request_id}),
        Unavailable { .. } => json!({"t": "onbeschikbaar"}),
        VolumeChanged { volume } => json!({"t": "volume", "v": procent(volume)}),
        ShuffleChanged { shuffle } => json!({"t": "shuffle", "aan": shuffle}),
        RepeatChanged { context, track } => json!({"t": "herhaal", "lijst": context, "nummer": track}),
        SessionConnected { user_name, .. } => json!({"t": "verbonden", "gebruiker": user_name}),
        SessionDisconnected { .. } => json!({"t": "los"}),
        SessionClientChanged { client_name, .. } => json!({"t": "bediening", "naam": client_name}),
        TrackChanged { audio_item } => {
            let (artiesten, album) = match &audio_item.unique_fields {
                UniqueFields::Track { artists, album, .. } => {
                    (artists.iter().map(|a| a.name.clone()).collect::<Vec<_>>(), album.clone())
                }
                UniqueFields::Episode { show_name, .. } => (vec![show_name.clone()], String::new()),
                UniqueFields::Local { artists, album, .. } => {
                    (artists.iter().cloned().collect(), album.clone().unwrap_or_default())
                }
            };
            // middelgrote hoes (de grootste is onnodig zwaar voor een klein plaatje)
            let hoes = audio_item
                .covers
                .iter()
                .filter(|c| c.width >= 200)
                .min_by_key(|c| c.width)
                .or(audio_item.covers.first())
                .map(|c| c.url.clone());
            json!({"t": "nummer", "id": audio_item.track_id.to_string(), "naam": audio_item.name,
                   "artiesten": artiesten, "album": album, "hoes": hoes, "duur": audio_item.duration_ms})
        }
        _ => return None,
    })
}

fn apparaat_id(naam: &str) -> String {
    Sha1::digest(naam.as_bytes()).iter().map(|b| format!("{b:02x}")).collect()
}

async fn commando(regel: &str, spirc: &Option<Spirc>) {
    let Some(spirc) = spirc else { return };
    let mut delen = regel.split_whitespace();
    let waarde = |d: Option<&str>| d.and_then(|v| v.parse::<u32>().ok());
    let r = match delen.next() {
        Some("play") => spirc.play(),
        Some("pause") => spirc.pause(),
        Some("playpause") => spirc.play_pause(),
        Some("next") => spirc.next(),
        Some("prev") => spirc.prev(),
        Some("volume") => match waarde(delen.next()) {
            Some(p) => spirc.set_volume((p.min(100) * 65535 / 100) as u16),
            None => Ok(()),
        },
        Some("seek") => match waarde(delen.next()) {
            Some(ms) => spirc.set_position_ms(ms),
            None => Ok(()),
        },
        Some("shuffle") => spirc.shuffle(waarde(delen.next()) == Some(1)),
        Some("repeat") => spirc.repeat(waarde(delen.next()) == Some(1)),
        _ => Ok(()),
    };
    if let Err(e) = r {
        log::warn!("commando '{regel}': {e}");
    }
}

#[tokio::main]
async fn main() {
    env_logger::Builder::new()
        .filter_level(log::LevelFilter::Warn)
        .filter_module("librespot", log::LevelFilter::Info)
        .filter_module("dmxdesk_spotify", log::LevelFilter::Info)
        .target(env_logger::Target::Stderr)
        .init();

    let args: Vec<String> = std::env::args().collect();
    let arg = |naam: &str| args.iter().position(|a| a == naam).and_then(|i| args.get(i + 1)).cloned();
    let naam = arg("--name").unwrap_or_else(|| "DMXDesk".into());
    let cache_map = arg("--cache");
    let poort: u16 = arg("--zeroconf-port").and_then(|p| p.parse().ok()).unwrap_or(0);
    let start_volume = arg("--volume")
        .and_then(|v| v.parse::<u32>().ok())
        .map(|p| (p.min(100) * 65535 / 100) as u16)
        .unwrap_or(52428);

    let device_id = apparaat_id(&naam);
    let session_config = SessionConfig { device_id: device_id.clone(), ..SessionConfig::default() };
    let connect_config = ConnectConfig {
        name: naam.clone(),
        device_type: DeviceType::Speaker,
        initial_volume: start_volume,
        ..ConnectConfig::default()
    };
    let player_config = PlayerConfig { bitrate: Bitrate::Bitrate320, ..PlayerConfig::default() };
    let cache = cache_map.as_ref().and_then(|m| Cache::new(Some(m), Some(m), None, None).ok());
    let mut credentials: Option<Credentials> = cache.as_ref().and_then(Cache::credentials);

    // als speaker op het netwerk verschijnen (zoals Sonos)
    let mut discovery = match librespot_discovery::find(None).and_then(|backend| {
        Discovery::builder(device_id.clone(), session_config.client_id.clone())
            .name(naam.clone())
            .device_type(DeviceType::Speaker)
            .port(poort)
            .zeroconf_backend(backend)
            .launch()
    }) {
        Ok(d) => Some(d),
        Err(e) => {
            log::error!("Discovery is unavailable: {e}");
            None
        }
    };
    if discovery.is_none() && credentials.is_none() {
        log::error!("Discovery is unavailable and no credentials provided. Authentication is not possible.");
        std::process::exit(1);
    }

    let mixer: Arc<dyn Mixer> = Arc::new(DmxMixer(AtomicU16::new(start_volume)));
    let mut session = Session::new(session_config.clone(), cache.clone());
    let player = Player::new(player_config, session.clone(), mixer.get_soft_volume(), || Box::new(DmxSink));
    let mut events = player.get_player_event_channel();
    gebeurtenis(json!({"t": "klaar", "naam": naam, "volume": procent(start_volume)}));

    let mut spirc: Option<Spirc> = None;
    let mut spirc_task: Option<std::pin::Pin<Box<dyn std::future::Future<Output = ()>>>> = None;
    let mut verbinden = credentials.is_some();
    let mut pogingen: Vec<Instant> = vec![];
    let mut regels = BufReader::new(tokio::io::stdin()).lines();

    loop {
        tokio::select! {
            nieuw = async { discovery.as_mut().unwrap().next().await }, if discovery.is_some() => {
                match nieuw {
                    Some(c) => {
                        credentials = Some(c);
                        pogingen.clear();
                        if let Some(s) = spirc.take() { let _ = s.shutdown(); }
                        if let Some(t) = spirc_task.take() { t.await; }
                        if !session.is_invalid() { session.shutdown(); }
                        verbinden = true;
                    }
                    None => { log::error!("Discovery stopped unexpectedly"); std::process::exit(1); }
                }
            },
            _ = async {}, if verbinden && credentials.is_some() => {
                verbinden = false;
                if session.is_invalid() {
                    session = Session::new(session_config.clone(), cache.clone());
                    player.set_session(session.clone());
                }
                match Spirc::new(connect_config.clone(), session.clone(), credentials.clone().unwrap(),
                                 player.clone(), mixer.clone()).await {
                    Ok((s, t)) => { spirc = Some(s); spirc_task = Some(Box::pin(t)); }
                    Err(e) => {
                        log::error!("could not initialize spirc: {e}");
                        tokio::time::sleep(Duration::from_secs(5)).await;
                        verbinden = true;
                    }
                }
            },
            _ = async { spirc_task.as_mut().unwrap().await }, if spirc_task.is_some() => {
                spirc_task = None;
                spirc = None;
                log::warn!("Spirc shut down unexpectedly");
                gebeurtenis(json!({"t": "los"}));
                pogingen.retain(|t| t.elapsed() < Duration::from_secs(600));
                if pogingen.len() < 5 {
                    pogingen.push(Instant::now());
                    if !session.is_invalid() { session.shutdown(); }
                    verbinden = true;
                }
            },
            e = events.recv() => match e {
                Some(e) => if let Some(v) = gebeurtenis_van(e) { gebeurtenis(v) },
                None => break,
            },
            regel = regels.next_line() => match regel {
                Ok(Some(r)) => commando(r.trim(), &spirc).await,
                _ => break,          // stdin dicht: DMXDesk is weg
            },
        }
    }
    if let Some(s) = spirc {
        let _ = s.shutdown();
    }
    if let Some(t) = spirc_task {
        let _ = tokio::time::timeout(Duration::from_secs(2), t).await;
    }
}
