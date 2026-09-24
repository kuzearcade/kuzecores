# kuzecores

A [Custom Database](https://github.com/MiSTer-devel/Downloader_MiSTer/blob/main/docs/custom-databases.md)
for the MiSTer *downloader*, so that kuzearcade's cores arrive through
`update_all` like any other core, and show up in release trackers that read
`db.json.zip` files.

## Install

Either drop in the ready-made file:

1. Download `downloader_kuzearcade_kuzecores.zip` from
   <https://raw.githubusercontent.com/kuzearcade/kuzecores/db/downloader_kuzearcade_kuzecores.zip>
2. Extract `downloader_kuzearcade_kuzecores.ini` into the **root of the SD card**,
   next to `downloader.ini`.

or add these two lines to the bottom of `downloader.ini` yourself:

```ini
[kuzearcade/kuzecores]
db_url = https://raw.githubusercontent.com/kuzearcade/kuzecores/db/db.json.zip
```

Then run *update* or *update_all* as usual.

## What it installs

| | |
|---|---|
| `_Arcade/*.mra` | one per parent set |
| `_Arcade/_alternatives/_<Parent>/*.mra` | the clone and bootleg sets |
| `_Arcade/cores/*.rbf` | the core bitstreams |

### Cores

- [Arcade-NMK16_MiSTer](https://github.com/kuzearcade/Arcade-NMK16_MiSTer) —
  the NMK16 family: four bitstreams (Macross2, Gunnail, Raphero, Afega)
  covering 97 sets, 31 parents and 66 alternatives.
- [Arcade-SandScrp_MiSTer](https://github.com/kuzearcade/Arcade-SandScrp_MiSTer) —
  Sand Scorpion (FACE, 1992) on Kaneko VIEW2 / PANDORA / CALC1 hardware: one
  bitstream covering all three sets, the parent and two alternatives.
- [Arcade-JalecoMS1BCD_MiSTer](https://github.com/kuzearcade/Arcade-JalecoMS1BCD_MiSTer) —
  Jaleco Mega System 1 types B, C and D: one bitstream covering 16 sets,
  eight parents and eight alternatives.
- [Arcade-JalecoMS1Z_MiSTer](https://github.com/kuzearcade/Arcade-JalecoMS1Z_MiSTer) —
  Jaleco Mega System 1 type Z (Legend of Makai): one bitstream covering both
  sets, the parent and one alternative.

## How it is built

The two kinds of file are handled differently, because the database builder
forces the split:

- **`.mra` files live in this repository**, under `_Arcade/`. They have to:
  the builder opens every `.mra` it lists and reads `<rbf>`, `<setname>` and
  the ROM zip names out of it to tag the entry, so an `.mra` that exists only
  as a URL fails the build outright. All 97 of them come to 640 KB of text.
- **`.rbf` files do not.** They are listed in `external_files.csv`, pointing
  at the bitstream in the core's own repository, **pinned to a commit**.
  Nothing reads their content, so they need not be duplicated here, which
  keeps 17 MB of bitstream per release out of this repository while the
  downloader still delivers it to the SD card.

Pinning to a *commit* rather than a branch is the point of the `.rbf` half: a
branch URL would turn every recorded size and MD5 into a future mismatch the
moment that core is rebuilt.

Adding a core is one entry in `CORES` in `tools/update_external_files.py`.

`tools/update_external_files.py` does both halves: it copies the `.mra` files
in (removing any that disappeared upstream) and rewrites `external_files.csv`.

`.github/workflows/build_db.yml` runs
[theypsilon's DB template builder](https://github.com/theypsilon/DB-Template_MiSTer)
on every push to `main`, which writes `db.json.zip` and the drop-in `.ini` to
the `db` branch. `FINDER_IGNORE` keeps this repository's own `tools/` directory
out of the database; `README.md`, `LICENSE` and `.github/` are excluded by the
builder itself.

The result was built and checked locally before first publication: 101 files
and 26 folders, and the official `downloader_test.py` fetched all four
bitstreams from their pinned URLs.

## Updating after a core release

```bash
tools/update_external_files.py     # re-pin every core to its branch head and rehash
git commit -am "Update to <core> <release>"
git push                           # the workflow republishes the db branch
```

`--keep-pins` refreshes sizes and hashes without moving the pins, and `--check`
writes nothing and exits non-zero if the file is out of date.

## A note on file names

The `.rbf` files keep the names their repository publishes, such as
`Arcade-NMK16_Gunnail_20260919.rbf`, while the `.mra` files ask for
`<rbf>NMK16_Gunnail</rbf>`. That works: MiSTer's MRA loader tries both the bare
core name and the same name with an `Arcade-` prefix, and accepts a `_` or `.`
after it, so the dated release name resolves
(`Main_MiSTer/support/arcade/mra_loader.cpp`).

## Licence

This repository contains only the database configuration and the script that
generates it, under GPL-3.0. The cores it indexes are covered by the licences
in their own repositories, and no ROM data is distributed here or by the
database.
