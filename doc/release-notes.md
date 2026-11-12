BTGS Core version 1.0.0 (draft)
==============================

*Not released yet. This file collects the notes for the first release.*

BTGS Core 1.0.0 is the first release of the new BTGS chain: a Dash Core v24 base
with SHA-256d proof of work and the BTGS chain settings (see the README).

Notable changes
---------------

- New chain: SHA-256d block hash, BTGS network magic, ports and address prefixes
- Block reward 12 BTGS, 1/14 less every 157,680 blocks; dev fund paid first
  (25% -> 5%), then 70% smartnodes, 30% miners; no treasury
- Smartnode collateral 20,000 BTGS; BTGS quorums for ChainLocks and InstantSend
- Programs and data folder: btgsd, btgs-qt, btgs-cli, btgs-wallet, btgs-tx; ~/.btgscore, btgscore.conf

Release notes of the Dash Core versions this release is based on are in
[doc/release-notes/](release-notes/).
