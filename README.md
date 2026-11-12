BTGS Core
=========

BTGS Core is the full node and wallet software for the new BTGS chain: a
community relaunch of BTGS on a Dash Core v24 base, mined with **SHA-256d**
(the same ASIC miners as Bitcoin).

> **Status: in development.** There is no mainnet or public release yet.
> The chain settings below follow the community spec and can still change
> before launch. Do not use this software with real funds.

Repository: https://github.com/BTGS-Community/btgs-core

What is BTGS?
-------------

BTGS is a peer-to-peer digital currency. The new chain keeps the balances of
the old chain (snapshot) and adds what the Dash base brings:

- **Smartnodes** (Dash masternodes) that secure the network with
  **ChainLocks** and confirm payments in seconds with **InstantSend**
- **Governance voting** by smartnodes (without treasury payouts)
- **SHA-256d proof of work**, with a difficulty adjustment every block

Main settings
-------------

| | |
|---|---|
| Proof of work | SHA-256d |
| Block time | 200 seconds (432 blocks per day) |
| Block reward | 12 BTGS at launch, 1/14 less every 157,680 blocks (~1 year) |
| Reward split | dev fund first (25% at launch, 1 point less every 6,048 blocks, 5% floor), then 70% smartnodes, 30% miners |
| Treasury | 0% (no superblock payouts) |
| Smartnode collateral | 20,000 BTGS |
| Addresses | `B…` (normal), `M…` (multisig/script); testnet `t…` |
| Ports | P2P 19888, RPC 19881 (testnet 29888 / 29881) |
| Programs | `btgsd`, `btgs-qt`, `btgs-cli`, `btgs-wallet`, `btgs-tx` |
| Data folder | `~/.btgscore` (Windows `%APPDATA%\BTGSCore`), config file `btgscore.conf` |

The data folder and config file are different from the old chain's, so the
old and the new node can run side by side.

Build from source
-----------------

The build steps and dependencies are in [./doc/](/doc):

- **Linux**: [./doc/build-unix.md](/doc/build-unix.md)
- **macOS**: [./doc/build-osx.md](/doc/build-osx.md)
- **Windows**: [./doc/build-windows.md](/doc/build-windows.md)
- **FreeBSD / OpenBSD / NetBSD**: [./doc/](/doc)

Short version on Linux:

    ./autogen.sh
    ./configure --without-gui
    make -j$(nproc)

Releases will be reproducible [Guix](/contrib/guix) builds with published
checksums.

Testing
-------

Unit tests: `make check`, or a single suite with
`src/test/test_btgs --run_test=<suite>`. See [src/test/README.md](/src/test/README.md).

Functional tests (Python): `test/functional/test_runner.py`. See [/test](/test).

Development process
-------------------

- `btgs`: the stable branch (protected). Changes come in through pull requests.
- `btgs-dev`: daily development. Built and tested, but not guaranteed to be stable.

Never put keys, passwords or other secrets in commits: every push is posted
to the community's #dev-updates channel.

The general contribution workflow is described in [CONTRIBUTING.md](CONTRIBUTING.md),
and developer hints are in [doc/developer-notes.md](doc/developer-notes.md).

License and credits
-------------------

BTGS Core is released under the terms of the MIT license. See
[COPYING](COPYING) or https://opensource.org/licenses/MIT.

BTGS Core is built on the work of the Dash Core and Bitcoin Core developers.
