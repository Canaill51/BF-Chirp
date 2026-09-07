# Security Policy

## What this project is

`bfchirp` is an offline command-line tool. It reads Betaflight blackbox logs
from the local filesystem, computes numbers, and prints them. It runs no
service, opens no socket, and stores no credentials.

One script does reach the network: `scripts/fetch_upstream.py` downloads
pinned files from `raw.githubusercontent.com` into a gitignored `vendor/`
directory. It is a development aid and is never invoked by the analysis code.

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | yes       |

The project is pre-1.0 and there is no maintenance branch. Fixes land on
`main` and go out in the next release; there are no backports.

## Where the risk actually is

Worth knowing before reporting, and before running `bfchirp` on a log you did
not record yourself:

* **Log files are untrusted input.** `.csv` decoding goes through numpy and
  pandas, and `.bbl` decoding is handed to `blackbox_decode`, a separate
  GPL-3.0 program that is not part of this project. A malicious log is
  therefore mostly a question for those dependencies — but a parsing crash or
  a hang reachable from a crafted log is still worth reporting here.
* **`blackbox_decode` is located by searching well-known paths and `$PATH`**
  (see `src/bfchirp/decode.py`). On a machine where an attacker can write to
  any of those locations, `bfchirp` will execute what it finds. Use
  `--decoder PATH` if that matters to you.
* **`--workdir` is written to** with decoded CSVs derived from the input file
  names.

Vulnerabilities in Betaflight itself, or in `blackbox_decode`, belong upstream
rather than here.

## Reporting a vulnerability

Report privately through GitHub Security Advisories:
[**Report a vulnerability**](https://github.com/Canaill51/BF-Chirp/security/advisories/new).

Please do not open a public issue for something you believe is exploitable.

Include the version or commit, your platform and Python version, what you
expected, what happened, and a log file or minimal input that reproduces it if
you can share one.

What to expect: an acknowledgement within about a week, and an assessment of
whether the report is accepted, once someone has reproduced it. This is a
small project maintained in spare time — the honest answer is that response is
best-effort, not contractual. Accepted issues are fixed on `main` and credited
in the advisory unless you would rather not be.
