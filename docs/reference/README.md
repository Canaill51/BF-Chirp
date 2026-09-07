# Upstream reference

`bfchirp`'s correctness rests on facts about software it does not own: the
chirp generator in Betaflight, the blackbox log format, and the
`blackbox_decode` CLI. These pages record those facts in one place, so that a
question like "is `debug[2]` really deci-Hz?" has an answer with a citation
instead of an opinion.

| Page | Covers |
|---|---|
| [chirp-firmware.md](chirp-firmware.md) | The sweep generator, its path into the setpoint, the debug channels, the `chirp_*` parameters |
| [blackbox-format.md](blackbox-format.md) | Log structure, frame types, encoding, and the decoded column names |
| [blackbox-decode.md](blackbox-decode.md) | How `bfchirp` invokes the decoder, the full flag list, and the one flag that must stay off |
| [cli-variables.md](cli-variables.md) | Every Betaflight setting that affects a measurement, with real CLI names and ranges |
| [debug-modes.md](debug-modes.md) | How `debug_mode` works, and why `gyroUnfilt` is not one |
| [SOURCES.md](SOURCES.md) | The pinned upstream revisions every page above was checked against |

## Why nothing upstream is committed here

`bfchirp` is GPL-3.0-or-later, as are Betaflight and blackbox-tools, so
licence compatibility is not the obstacle — vendoring their files here would
be permitted. It is still the wrong thing to do.

A committed copy of someone else's source has no way to tell you it has gone
stale. It looks authoritative for exactly as long as it takes upstream to
change, and then it quietly starts lying. A citation plus a pinned commit
cannot do that: the pin either still matches or it does not, and
`--check` says which.

So these pages are **our own prose**. They describe, summarise and cite; they
do not reproduce. Where a formula or a line of code is quoted it is the short
excerpt needed to make the point, attributed to its file.

To read the real thing, fetch it on demand:

```sh
python scripts/fetch_upstream.py          # into vendor/upstream/, gitignored
```

## Keeping these pages honest

Upstream moves. A reference page that has silently stopped matching the
firmware is worse than no page at all, because it is trusted.

Every page ends with a **Sources** block naming the files it was derived from
and the commit they were read at. The pins live in
[`scripts/upstream_sources.json`](../../scripts/upstream_sources.json), and:

```sh
python scripts/fetch_upstream.py --check
```

re-fetches each pinned file at upstream `master` and reports which ones have
changed since. When it reports drift, re-read the affected pages, correct
them, and update the `commit` and `checked` fields in the manifest — in that
order. Bumping the pin without re-reading defeats the purpose.

`python scripts/fetch_upstream.py --list` prints the manifest as a table.

## Scope

These pages document *upstream*. Two neighbouring documents cover different
ground and should not absorb this material:

- [`docs/firmware.md`](../firmware.md) — what was verified against **real
  flight logs**, including measurements that upstream source alone cannot
  settle.
- [`README.md`](../../README.md) — what the resulting measurements can and
  cannot support.
