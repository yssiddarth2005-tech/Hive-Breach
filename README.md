# HIVE BREACH

A top-down twin-stick alien shooter that runs in any modern browser. Version 3.0 has two modes:

- **Story mode** with a chapter select. **Chapter 2: The Hive Tunnels** unlocks when you beat Chapter 1.
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

Progress is only saved when the game can reach the progress server (see `hive-breach-server/`). The live site and `http://localhost:8000` are allowed to connect; a double-clicked file is not, so it plays offline and nothing you unlock is kept.

The game picks its server from the address it was opened at:

| Opened at | Talks to |
|---|---|
| GitHub Pages, or anywhere else | `RENDER_URL` at the top of `game.js` (https://hive-breach-1.onrender.com) |
| the Render server itself | the same address (the server also serves `index.html`, `game.js`, `style.css`) |
| `http://localhost:10000` | the same address |
| any other `localhost` port (e.g. `python -m http.server 8000`) | `http://localhost:10000` |

### With the progress server (local)

```
cd hive-breach-server
pip install -r requirements.txt
python app.py                      # listens on http://localhost:10000 and serves the game there
```

Open `http://localhost:10000`. If the server isn't running the game still works, shows
**OFFLINE - PROGRESS WILL NOT BE SAVED**, and connects by itself once the server is up.
Database and secrets: see `hive-breach-server/README.md` (Neon setup, `.env`).

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
| B | Armory (endless: between waves; story: in the corridor after you pick a mutation) |
| Tab / Q / E, W S | In the Endless Armory: switch tabs, pick a weapon on the WEAPONS tab |
| T | Drop an auto-turret (buy them in the Armory, max 3) |
| 1 2 3 / R | Story mode: choose a mutation card / reroll the cards (once per chapter) |
| Enter / Space | Skip the cinematic or the boss intro |
| Esc / P | Pause menu |
| M | Mute |

### Touch (phones and tablets)

Hold the phone sideways; in portrait the game asks you to rotate it. The first tap goes fullscreen where the browser allows it. Switching apps drops fullscreen; tap the fullscreen button (next to pause in a fight, top-right corner elsewhere) to get it back. Settings and the pause menu also have a fullscreen on/off option, on PC too.

| Touch | Action |
|---|---|
| Left thumb anywhere on the left side | Move stick appears under your thumb. Drag past its rim to sprint (after buying sprint) |
| Right thumb on the right side | Aim stick: aims, and fires while pushed |
| DASH, RLD, SWAP | Dash, reload, next weapon |
| DUAL / ONE, BOT, TUR, STRK | Shown only when they apply: dual pistols, bot decoy, drop a turret, orbital strike |
| II (top centre) | Pause |
| Corner brackets next to II | Fullscreen on / off |
| < BACK (top left) | Back one screen: menus, the Armory, the pause menu |
| ARMORY icon, NEXT WAVE | Appear after you clear a wave |
| TALK, REROLL | Appear when you can use them |

Menus, the Armory, mutation cards and dialogs work by tapping. Use the game's own **< BACK** button rather than the phone's back gesture: the phone's back always drops fullscreen first. When the game isn't fullscreen, the phone's back gesture also steps back one screen (or pauses a fight) instead of leaving the page.

**Customize the layout:** *How to Play > Customize phone layout.* Drag any control to move it, change button size, stick size and opacity, and choose floating sticks (they appear where your thumb lands) or fixed sticks. Saved on that device; *Reset* puts everything back. *How to Play* has separate pages for PC and phone controls, and the phone page shows your current layout.

## Test panel

Only when the game is opened from this computer (`localhost`) or your home network (`192.168.x.x`, `10.x.x.x`, `172.16-31.x.x`); it never appears on the live site. Press `` ` `` (left of 1) or tap **TEST** on the left edge.

It has god mode, +5000 credits, all weapons with full ammo, full health, kill all enemies, finish the current boss stage, jump to any wave, spawn any enemy or boss, and game speed (0.25x to 2x). Using any tool stops that run from being saved to the server.

To try it on your phone: run the server on your computer (`python app.py` in `hive-breach-server`), connect the phone to the same Wi-Fi, and open `http://<your computer's IP>:10000`. Progress isn't saved there (the server only accepts the live site and `localhost`), which is fine for testing.

## Tuning the game

Most balance lives in a few tables near the top of `game.js`:

- **Weapons:** `WEAP` (damage, fire rate, spread, magazine, reload, ammo, unlock price) and `LASER_PISTOL` for the pistol's Mk II.
- **Weapon stages and attachments:** `WSTAGE` (what Mk II and Mk III add), `MK_COST` (evolve prices), `applyStage` (stat changes per stage), `ATT` (every attachment's name, text and price). Their effects live in `fire()`, the bullet loop, `fireSniper` and the helpers `shotFx`, `ricochet`, `chill`, `miniBlast` and `addPMine`.
- **Enemies and bosses:** `ET` (radius, health, speed, damage, credit drop, colours).
- **Waves:** `buildWave(n)` sets each wave's size and enemy mix; `isBossWave(n)` picks boss waves.
- **Story rooms:** `CH1` lists each room's enemy counts, spawn cap and rate, and Dr. Voss's lines; `ROOM_DEFS` holds the layouts.
- **Perks:** `PERKS` (name, rarity, text, stat rows) and `RAR` (rarity colours and roll weights). Effects are wired up with `perkOn('name')`.
- **Boss stage 2:** `BOSS2` (health, size, speed, damage, title); attack choices live in `queen2` and `zero2`.
- **Armory prices:** `SHOP`, `upCost`, `wInfo`, `evoInfo`, `ATT` and `botInfo`.
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

## What changed in 2.6

- First server save (replaced in 2.7: it still trusted whatever the browser sent).

## What changed in 2.7

- **Progress lives on the server and is verified there.** Chapters, skins, Alien Codex entries and best score are no longer read from or written to `localStorage`, so editing it in the console unlocks nothing. The game reports what happens during a run (rooms, kills, bosses, waves, score) over a WebSocket, and the server (`hive-breach-server/`) checks each report against the game's rules and its own clock before granting anything. Equipping a skin goes through the server too and is refused if you haven't earned it.
- HTTP is used only for rare actions (creating your anonymous player, loading progress, equipping a skin). Kills are batched into one small WebSocket message per second, so play isn't slowed down.
- The main menu shows the connection state. Offline (or opened straight from disk), the game still plays, but anything you unlock lasts only for that session.
- The debug/filming API (`window.__hb`) is no longer included in release builds.
- `localStorage` now holds only your player token and your audio/difficulty options (plus, from 2.8, the names of your Chapter 1 mutations).

## What changed in 2.8

- **Armory only between fights.** In Endless Siege, B opens the Armory only after a wave is cleared. In story mode, it opens only in the corridor after you pick a mutation card. Pressing B mid-fight shows a short notice instead.
- **Chapter 2 is locked** on the chapter select until you beat Chapter 1. The *Play anyway (testing)* button is gone.
- **Mutations carry over.** The mutation cards you picked in Chapter 1 come with you into Chapter 2 (Thick Skin's +30 max HP included), and Chapter 2 only offers mutations you don't have yet. They're remembered for later visits too, so starting Chapter 2 from the menu also brings them.
- **Continue straight into Chapter 2.** On the Chapter 1 summary, Enter now continues to Chapter 2 (Esc goes to the main menu, E to Endless Siege).
- **Chapter 2 opening cutscene.** About 20 seconds in four shots before the chapter card: Specimen Zero's shattered tube, the service-lift ride down, infected workers in the tunnels, and Zero crossing the far cavern. Space or Enter skips it.

## What changed in 2.9

- **Touch controls.** Play on a phone or tablet held sideways: a move stick and an aim-and-fire stick that appear under your thumbs, buttons for dash, reload and weapon swap, and context buttons (Armory, next wave, pause, talk, reroll) when they apply. Menus and the Armory work by tapping.
- **Customizable phone layout** in *How to Play*, which now has separate PC and phone pages. Choose floating or fixed sticks.
- **Fullscreen on/off** button on phones, plus a fullscreen option in Settings and the pause menu.
- **BACK button** on every phone screen you can leave, so you never need the phone's back gesture (which drops fullscreen).
- **Armory icon after each wave.** Clearing a wave no longer pops the Armory open: an Armory icon and a NEXT WAVE button appear instead (click or tap them, or use B and Enter).
- **Test panel** for local testing only (see *Test panel* above).

## What changed in 3.0

- **Weapon stages (Endless Siege).** Every weapon now goes Mk I, Mk II, Mk III. Max its DMG and RATE (the sniper: DMG and RANGE), then EVOLVE it in the Armory (Mk II 220 credits, Mk III 420). Each stage changes how the gun looks in the marine's hands and its icon (Mk II adds hardware and two cyan chevrons; Mk III a glowing aura, sparks and three gold chevrons, also shown above the weapon panel during a fight), raises its stats, and lets its upgrades go higher (4, then 6, then 8). Upgrades cost 45 credits plus 18 per level, so maxing one weapon to Mk III costs about 2,370 credits, around wave 10 of a normal run:
  - Pistol: Laser pistol (piercing bolts, the old level 2), then Plasma pistol (every 4th shot bursts).
  - Shotgun: Double barrel (+2 pellets, 8 shells), then Drum mag (12 shells, pellets ignite).
  - Minigun: Twin barrels (+150 belt), then Incendiary belt (hits can burn).
  - Flamer: Long nozzle (+30% range), then Blue flame (double damage).
  - Launcher: 6-round drum and bigger blast, then shells split into 3 bomblets.
  - Sniper: pierces 5 aliens, then kills explode.
  - Rifle: 40-round mag and faster, then every 10th round explodes.
- **Attachments.** Two slots per weapon with two choices each (110 to 220 credits); slot 1 opens at Mk I, slot 2 at Mk II. Buy an attachment once, then swap between the ones you own for free.

  | Weapon | Slot 1 | Slot 2 |
  |---|---|---|
  | Pistol | Ricochet rounds / Extended mag | Hair trigger / Hollow points |
  | Shotgun | Slug barrel / Wide choke | Dragon's breath / Flechettes |
  | Minigun | Stabilizer / Drum | Tesla coil / Shredder |
  | Flamer | Napalm tank / Wide nozzle | Cryo swap / Pressure pump |
  | Launcher | Cluster shells / Sticky mines | Big payload / Quick loader |
  | Sniper | Rail core / Mark scope | Fast bolt / Explosive tip |
  | Rifle | Burst trigger / AP rounds | Extended mag / Tracer |

- **New Armory.** Three tabs (SUPPLIES, WEAPONS, BOT AND DASH). On WEAPONS, pick a weapon on the left to see its stage path, upgrades, EVOLVE button and attachments. Bigger buttons that work by touch. Story mode keeps its own Armory and isn't affected.
- **Test panel:** *All weapons Mk II* and *All weapons Mk III + own all attachments*, for trying every stage and combination quickly.
