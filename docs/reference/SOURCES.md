# Pinned upstream sources

Every page in this directory was written against specific revisions of
upstream code and documentation. This is the record of which ones.

The machine-readable manifest is
[`scripts/upstream_sources.json`](../../scripts/upstream_sources.json) — the
single source of truth. The table below is generated from it by
`python scripts/fetch_upstream.py --list`.

| Upstream | Licence | Pinned commit | Checked | Files |
|---|---|---|---|---|
| [betaflight](https://github.com/betaflight/betaflight) | GPL-3.0 | `61b2c9f6d98d` | 2026-09-08 | `src/main/common/chirp.c`<br>`src/main/common/chirp.h`<br>`src/main/flight/pid.c`<br>`src/main/build/debug.c`<br>`src/main/build/debug.h`<br>`src/main/cli/settings.c`<br>`src/main/fc/parameter_names.h`<br>`src/main/blackbox/blackbox.c`<br>`src/main/blackbox/blackbox_fielddefs.h` |
| [blackbox-tools](https://github.com/betaflight/blackbox-tools) | GPL-3.0 | `f832acf9cd9d` | 2026-09-08 | `src/blackbox_decode.c`<br>`Readme.md` |
| [betaflight.com](https://github.com/betaflight/betaflight.com) | unspecified | `f05cf72c7f48` | 2026-09-08 | `docs/development/Blackbox-Internals.md`<br>`docs/development/debugging/Debug-Field-Annotations.md` |

## Working with these

```sh
python scripts/fetch_upstream.py           # download the pinned revisions
python scripts/fetch_upstream.py --check   # report drift against master
python scripts/fetch_upstream.py --list    # regenerate the table above
```

Files land in `vendor/upstream/<repo>/<path>`, which is gitignored. Nothing
from these repositories is committed — not for licence reasons (everything
here is GPL-3.0) but because a committed copy cannot tell you when it has
gone stale. See [README.md](README.md#why-nothing-upstream-is-committed-here).

## Which page cites what

| Page | Derived from |
|---|---|
| [chirp-firmware.md](chirp-firmware.md) | `common/chirp.c`, `common/chirp.h`, `flight/pid.c`, `cli/settings.c`, `fc/parameter_names.h`, `blackbox/blackbox.c` |
| [blackbox-format.md](blackbox-format.md) | `Blackbox-Internals.md`, `blackbox/blackbox.c`, `blackbox/blackbox_fielddefs.h` |
| [blackbox-decode.md](blackbox-decode.md) | `src/blackbox_decode.c`, `Readme.md` |
| [cli-variables.md](cli-variables.md) | `cli/settings.c`, `fc/parameter_names.h`, `flight/pid.c`, `blackbox/blackbox.c`, `blackbox/blackbox_fielddefs.h` |
| [debug-modes.md](debug-modes.md) | `build/debug.h`, `build/debug.c`, `flight/pid.c`, `Debug-Field-Annotations.md` |

## Other references

- [PR #13105](https://github.com/betaflight/betaflight/pull/13105) — the pull
  request that added the chirp generator. The design discussion there is
  context the source alone does not carry.
- [Blackbox Internals](https://betaflight.com/docs/development/Blackbox-Internals)
  — rendered version of the format documentation.
- [blackbox-tools](https://github.com/betaflight/blackbox-tools) — source of
  `blackbox_decode`.
