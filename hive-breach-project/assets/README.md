# HIVE BREACH - assets

The game itself does not load any of these files. It draws every sprite and synthesizes every sound in code (`game.js`) each time it runs. These are exports of exactly what the game generates, rendered from the game's own drawing and audio functions. Use them for thumbnails, store pages, social posts, devlogs or as a starting point if you ever move to a game engine.

## sprites/

- `enemies/<type>/` has four animation frames per enemy (`<type>_0.png` to `<type>_3.png`) plus a horizontal sprite sheet `<type>_sheet.png`. They are rendered at 3x game size, facing right, on a transparent background.
  Types: brute, bulwark, crawler, exploder, flyer, mender, mite, node, phantom, queen, runner, spitter, splitter, tunneler, zero.
  (`node` is Specimen Zero's shield heart node, `mite` is what a Splitter bursts into, `zero` is Specimen Zero, `queen` is the Hive Queen.)
- `bosses_stage2/` has the evolved second-stage bosses, four frames each at 3x: `crimson_empress/` (the Hive Queen after she ascends) and `zero_unbound/` (Specimen Zero after it sheds its shell).
- `player/` has the marine holding each weapon: pistol, dual pistols, laser pistol, dual laser pistols, shotgun, minigun, flamer, launcher, sniper and rifle. Also 3x, facing right.

## ui/

- `logo.png` is the HIVE BREACH title logo, transparent background, 1900 x 560.
- `icons/` has the Armory and HUD icons at 192 x 192: ammo, ammo1, bolt, bot, dmg, flamer, heart, laserpistol, launcher, lock, maxhp, medkit, minigun, pistol, range, rate, rifle, shotgun, sniper, sprint, star.

- `perks/` has the 12 story-mode mutation icons at 192 x 192, ringed in their rarity colour (green common, blue rare, orange epic): ricochet, vampiric, blazing, bot, skin, reload, chain, adrenaline, scavenger, acidblood, secondwind, magnet.

## map/

- `sublevel9_floor_and_walls.png` is the full 2400 x 1800 lab map (floor, sector markings, walls, tanks, racks, benches, vents and blast doors) as baked at startup. Crates, barrels and blood are added during play and aren't included.
- `minimap.png` is the 160 x 120 minimap base.
- `story/` has the six Chapter 1 maps as baked at load time: `room1_quarantine_wing`, `room2_bio_lab`, `room3_cryo_storage`, `room4_server_core`, `room5_reactor_control` and `boss_arena_the_nest` (the larger 3000 x 2160 Hive Queen arena).

## fx/

- `glow_white.png`, `glow_red.png` and `glow_green.png` are the radial glow sprites used for lights, alarms, tanks and explosions.

## audio/

- `sfx/` has all 65 sound effects as 44.1 kHz mono WAV, normalised.
- `music/` has the seven soundtrack loops, about 12 to 19 seconds each: `music_menu`, `music_ambient` (normal waves and story rooms), `music_chapter` (opening cinematic, chapter card and perk screens), `music_queen`, `music_queen2` (Crimson Empress, boss stage 2), `music_zero` and `music_zero2` (Zero: Unbound, boss stage 2). The game generates its music live with slight random variation, so each playthrough sounds a little different from these recordings.

## Not exported as separate files

Bullets, lasers, flames, pickups, crates, barrels, the combat bot, particles and the HUD panels are drawn directly inside the world and HUD rendering code rather than by a reusable function. You can see them in the promo screenshots in the `promo` folder.
