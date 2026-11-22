# HIVE BREACH

A top-down twin-stick alien shooter that runs in any modern browser. Version 2.5 has two modes:

- **Story mode** with a chapter select. **Chapter 2: The Hive Tunnels** unlocks when you beat Chapter 1 (or pick *Play anyway* to try it early).
- **Chapter 1: Containment Failure.** An opening cinematic, an animated chapter card, five rooms fought one after another, a mutation (perk) card choice after every room, and a final fight against the Hive Queen in her nest. If you die you restart from the beginning of the room you were in.
- **Endless siege, Sublevel 9.** Survive 20 waves in a sealed lab, kill the Hive Queen (wave 10) and Specimen Zero (wave 20), then keep going.

Both bosses fight in two stages. When the first health bar empties the boss evolves into a new creature with new attacks and its own music: the Hive Queen becomes **The Crimson Empress** and Specimen Zero becomes **Zero: Unbound**.

Everything is plain HTML, CSS and JavaScript on a 2D canvas. There are no libraries, no build step and no image or audio files: the game draws every sprite and synthesizes every sound at runtime.

## Play online

**https://yssiddarth2005-tech.github.io/Hive-Breach/**

## Run it

- Double-click `index.html`, or
- serve the folder with any static server (for example `python -m http.server`) and open `http://localhost:8000`.

Click the game once so the browser allows keyboard input and sound.

## Project structure

```
hive-breach-project/
  index.html     page shell: one <canvas> plus the two files below
  style.css      full-screen canvas styling
  game.js        the entire game (about 4,500 lines, one self-contained script)
  assets/        PNG and WAV exports of everything the game generates (see assets/README.md)
```

The original single-file version (`hive-breach.html`, everything inlined) is in the parent folder and behaves identically.

## How game.js is organised

The top of `game.js` has a table of contents with line numbers. In order:

| Section | What it does |
|---|---|
| screen | Canvas sizing and the logical-to-screen scale |
| options | Music, sound effects, screen shake and difficulty, saved to localStorage |
| audio | Web Audio synth (`tone`, `noise`) and every sound effect in `sfx(name)` |
| procedural music | Seven step-sequenced tracks: menu, waves, story chapter, and two stages for each boss |
| map system | `buildMap(def)` loads any layout; `LAB` is the 40 x 30 endless lab |
| baked floor | Renders the floor and fixtures once to an offscreen canvas; blood decals go on a second layer |
| game data | Weapon table `WEAP`, enemy table `ET`, run state, `buildWave`, `startWave` |
| collision + pathing | Tile collision and a flow field so the swarm walks around walls |
| combat bot | Roaming bot AI, decoy, stage 2 trooper, bot shop entries |
| boss helpers | Boss senses (distance, hiding, dashing, reloading), throws, debris rain, death sequence |
| boss stage 2 | Evolution sequence, Crimson Empress and Zero: Unbound attacks, telegraphed hazards (acid rain, laser lattice, singularity, shockwaves), boss title cards |
| fx helpers | Particles, explosions, pickups, crates, damage and kill handling |
| player actions | Firing, reloads, dash, dual pistols, laser sight, Armory items and upgrades |
| main menu | Menu screens and pause menu |
| input | Keyboard, mouse and scroll handling |
| update | One 1/60 s simulation step: player, director, enemy and boss AI, bullets, pickups |
| drawing | World, sprites, effects, HUD, Armory, menus and logo |
| stage 2 boss sprites, perk icons | Drawing code for the evolved bosses and the 12 mutation icons |
| story mode | Room layouts (`ROOM_DEFS`), chapter script (`CH1`), perks (`PERKS`), story director, checkpoints, boss intro, opening cinematic, chapter card, perk and corridor screens |
| main loop | Fixed-timestep loop on `requestAnimationFrame` |

## Controls

| Key | Action |
|---|---|
| W A S D | Move |
| Mouse | Aim |
| Left click (hold) | Fire |
| R | Reload |
| 1 - 7 or scroll | Switch weapon |
| E | Toggle single or dual pistols |
| Space | Dash (brief invincibility; hurts aliens with Dash Strike; faster/further with Dash Speed and Dash Range) |
| Hold F | Story mode: work objectives (switches, valves) and talk to Dr. Voss |
| G | Story mode: call an orbital strike at the cursor (bought in the Armory) |
| Shift | Sprint (after buying it) |
| Q | Combat bot decoy |
| B | Armory |
| T | Drop an auto-turret (buy them in the Armory, max 3) |
| 1 2 3 / R | Story mode: choose a mutation card / reroll the cards (once per chapter) |
| Enter / Space | Skip the cinematic or the boss intro |
| Esc / P | Pause menu |
| M | Mute |

## Tuning the game

Most balance lives in a few tables near the top of `game.js`:

- **Weapons:** `WEAP` (damage, fire rate, spread, magazine, reload, ammo, unlock price) and `LASER_PISTOL` for the level 2 pistol.
- **Enemies and bosses:** `ET` (radius, health, speed, damage, credit drop, colours).
- **Waves:** `buildWave(n)` sets each wave's size and enemy mix; `isBossWave(n)` picks boss waves.
- **Story rooms:** `CH1` lists each room's enemy counts, spawn cap and rate, and Dr. Voss's lines; `ROOM_DEFS` holds the layouts.
- **Perks:** `PERKS` (name, rarity, text, stat rows) and `RAR` (rarity colours and roll weights). Effects are wired up with `perkOn('name')`.
- **Boss stage 2:** `BOSS2` (health, size, speed, damage, title); attack choices live in `queen2` and `zero2`.
- **Armory prices:** `SHOP`, `upCost`, `wInfo` and `botInfo`.
- **Difficulty presets:** `DIFFS`.

## Debug API

`window.__hb` exposes game state and a few hidden helpers that were used to film the promo videos. Examples: `director` (pause wave spawning), `bossCmd('leap' | 'beam' | ...)` (trigger a boss ability), `spawn(type, x, y)` and `startWave(n)`. Normal play never touches them. Delete the `window.__hb = ...` block near the end of `game.js` if you don't want them.

## What changed in 2.0

- Story mode, Chapter 1: opening cinematic, animated chapter card, 5 rooms, 12 mutation cards, room checkpoints, the Nest arena (larger than the lab, with a lights-out boss reveal) and a chapter summary.
- Two-stage bosses with evolution sequences, new forms, new attack sets and new music.
- Brutes speed up the longer they live (+0.25x every 5 seconds, up to 2x) and glow hotter as they do.
- Menders now also make nearby aliens 35% faster, as well as healing them.
- Heavy sniper toned down: 150 base damage, hits at most 3 aliens per shot (100% / 60% / 35%), slightly slower to fire.
- New Armory item, Dash Strike (3 levels): dashing through aliens hits them for 60 / 95 / 140 damage.

## What changed in 2.1

- Boot splash: click to enter, then the HIVE BREACH title is stamped onto the screen with its own music sting before the main menu. (Browsers only allow sound after a click, which is why the first screen asks for one.)
- Main menu buttons play a soft blip when the mouse moves over them.
- Story mode opens with title cards, then the cinematic, then a playable scene: walk to the control room window and talk to Dr. Voss (pick your questions). She now has a synthesized radio voice.
- Every story room has a unique objective, and aliens keep spawning until it is done: restore power, recover samples, reboot the cryo console, destroy hive nodes, stop the reactor meltdown.
- Story Armory: the small damage and fire-rate upgrade levels are gone. Credits buy big-ticket items instead: Weapon Overclock (all weapons), Nano Armor, Orbital Strike charges, Extra Life, Combat Bot and Bot Mk-II, Laser Pistol, weapon unlocks (including the Heavy Sniper) and the dash upgrades.
- Sprint is unlocked from the start in story mode.
- Dash Strike damage lowered to 22 / 34 / 48. New Dash Speed (faster dash, shorter recharge) and Dash Range (longer dash) upgrades, in both modes.
- Crates can hold a magnet power-up that pulls every credit and pickup within range to you for 20 seconds.

## What changed in 2.2

- New mutation cards replace Scavenger and Magnetic Field: **Mirror Decoy** (each dash leaves a hologram that pulls nearby aliens to it, then explodes) and **Orbital Blades** (three energy blades orbit you and shred anything close).
- Single pistol: 24 damage, tighter aim and a 20% chance to crit for double damage. Dual pistols fire faster but each shot does 30% less damage.
- How to Play now shows drawn keycaps and mouse icons for every control.

## What changed in 2.3

- **Fusion.** When the room gets overcrowded, 7 to 10 nearby aliens merge into an **Amalgam**: a hunched, humanoid alien built from their bodies that inherits 2 or 3 of their abilities (pounce, acid spray, charge, spike nova, blink, regen, armor, split, cloak). A siren, a red alert banner and the fusion music play while they merge, and killing enough of them first stops it (+75 credits). Story mode: up to 2 per room. Endless: from wave 6, up to 2 per wave (3 from wave 12).
- **Alien Codex** on the main menu: every alien, the Amalgam and both forms of each boss. Entries stay hidden until you kill one, and are saved in your browser.
- **Skins** on the main menu, earned by achievements, each with its own ability: Crimson Warden (kill the Hive Queen: acid does 50% damage), Void Walker (kill Specimen Zero: longer, safer dash), Swarm Breaker (kill an Amalgam: shockwave every 25 kills), Hazmat Responder (finish Chapter 1: slow health regen, stronger medkits).

## What changed in 2.4

- **Chapter 2: The Hive Tunnels.** Five carved caverns with organic rock walls instead of lab rooms, each with a new task:
  - *Collapsed Tunnel*: escort Private Hale to the exit and keep the infected off him.
  - *Hive Pillars*: grab demolition charges and blow up three hive pillars.
  - *Drill Site*: defend a mining drill for 45 seconds and hold F to repair it.
  - *Burrow Network*: hunt down a Carrier that runs from you and seeds crawlers.
  - *The Dark Deep*: pitch black; light four flare beacons with only your flashlight.
- **New enemies.** Infected humans (Infected Worker lunges and slows you, Infected Soldier fires rifle bursts, Infected Sapper plants proximity mines), the Blighter (leaves and lobs acid pools) and the Carrier.
- **Zero's Lair.** Specimen Zero fights in his own arena with broken containment tubes, cyan crystals, conduits and his empty "SPECIMEN 0" tube.
- **Auto-turret.** Buy it in either Armory (250 credits), press **T** to drop it. Up to 3 at a time; it shreds aliens at short range until it is destroyed or you leave the room.
- Chapter select screen, chapter progress saved in your browser, new Codex entries for all five new enemies.

## What changed in 2.5

- **Performance fix.** The Alien Codex, Skins screen and the Chapter 2 opening card were dropping to around 10 FPS because they redrew every creature's full procedural artwork from scratch every single frame. Those screens now render each creature once to a small cached image and reuse it, so they run at full framerate.
- The Chapter 2 opening card used a brute-force full-screen color filter to retint it cyan, which was the main cause of its slowdown; it's now colored directly instead, and looks the same (or better) at full speed.
