#!/usr/bin/env python3
# Copyright (c) 2026 The BTGS Community developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Make the keys for a BTGS testnet (run once, on your own server, outside the git repo).

Makes: 1 spork key, 3 dev fund keys (2-of-3 multisig address), and a "bank" of keys that the testnet snapshot
list pays in block 1 (default: 30 x 20,000 test BTGS = exactly one smartnode collateral each, plus 5 x 1,000).
Prefixes are read from the testnet section of src/chainparams.cpp, so addresses match the node.

NEVER prints a private key. Secrets go to <out>/secret-keys.txt (mode 600). Public values go to <out>/public.txt
and the snapshot list to <out>/btgs-snapshot-testnet.csv (safe to share/commit).
Refuses to run if the output folder already exists (so existing keys can never be overwritten).

Usage:  python3 contrib/snapshot/make-testnet-keys.py [--out ~/btgs-testnet-keys] [--chainparams src/chainparams.cpp]"""
import argparse, os, re, secrets, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from btgs_migrate_keys import N, pubkey, hash160, b58check

COIN = 100_000_000

def prefixes(path):
    s = open(path).read()
    i0 = s.find("class CTestNetParams"); i1 = s.find("class CDevNetParams")
    if i0 < 0 or i1 < i0: sys.exit("testnet section not found in " + path)
    seg = s[i0:i1]; out = {}
    for name in ("PUBKEY_ADDRESS", "SCRIPT_ADDRESS", "SECRET_KEY"):
        m = re.search(r"base58Prefixes\[" + name + r"\]\s*=\s*std::vector<unsigned char>\(1,\s*(\d+)\)", seg)
        if not m: sys.exit(f"{name} not found in the testnet section")
        out[name] = int(m.group(1))
    return out

def newkey(): return secrets.randbelow(N - 1) + 1
def wif(k, v): return b58check(bytes([v]) + k.to_bytes(32, "big") + b"\x01")
def p2pkh(k, v): h = hash160(pubkey(k)); return b58check(bytes([v]) + h), h.hex()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.expanduser("~/btgs-testnet-keys"))
    ap.add_argument("--chainparams", default="src/chainparams.cpp")
    ap.add_argument("--big", type=int, default=30); ap.add_argument("--small", type=int, default=5)
    a = ap.parse_args()
    if os.path.exists(a.out): sys.exit(f"STOP: {a.out} already exists - not touching existing keys")
    px = prefixes(a.chainparams)
    if px["PUBKEY_ADDRESS"] != 127: sys.exit("STOP: testnet address prefix is not 127 ('t') - wrong chainparams?")
    os.makedirs(a.out, mode=0o700)
    secret, public, rows = [], [], []

    sk = newkey(); sa, _ = p2pkh(sk, px["PUBKEY_ADDRESS"])
    secret.append(f"SPORK_KEY {wif(sk, px['SECRET_KEY'])}  # {sa}")
    public.append(f"SPORK_ADDRESS {sa}")

    dev = [newkey() for _ in range(3)]
    pubs = [pubkey(k) for k in dev]
    redeem = b"\x52" + b"".join(bytes([len(p)]) + p for p in pubs) + b"\x53\xae"        # OP_2 <3 pubkeys> OP_3 OP_CHECKMULTISIG
    dev_addr = b58check(bytes([px["SCRIPT_ADDRESS"]]) + hash160(redeem))
    for i, k in enumerate(dev, 1): secret.append(f"DEV_KEY_{i} {wif(k, px['SECRET_KEY'])}")
    public += [f"DEV_FUND_ADDRESS {dev_addr}  # 2-of-3 multisig (P2SH)", f"DEV_FUND_REDEEMSCRIPT {redeem.hex()}"]

    total = 0
    for kind, count, amount in (("BANK_20000", a.big, 20000), ("BANK_1000", a.small, 1000)):
        for i in range(1, count + 1):
            k = newkey(); addr, h = p2pkh(k, px["PUBKEY_ADDRESS"])
            secret.append(f"{kind}_{i} {wif(k, px['SECRET_KEY'])}  # {addr}")
            public.append(f"{kind}_{i} {addr} {amount}")
            rows.append(f"{addr},{amount * COIN},{h},testnet-bank"); total += amount

    def write(name, text, mode):
        fd = os.open(os.path.join(a.out, name), os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(fd, "w") as f: f.write(text)
    write("secret-keys.txt", "# BTGS TESTNET SECRET KEYS - never commit, never paste, never send\n" + "\n".join(secret) + "\n", 0o600)
    write("public.txt", "# Public values (safe to share)\n" + "\n".join(public) + f"\nTOTAL_SNAPSHOT {total} BTGS in {len(rows)} outputs\n", 0o644)
    write("btgs-snapshot-testnet.csv", "# new_address,amount_sats,hash160,old_addresses\n" + "\n".join(rows) + "\n", 0o644)
    print(f"Folder: {a.out} (mode 700)")
    print(f"  spork address:    {sa}")
    print(f"  dev fund address: {dev_addr}  (2-of-3)")
    print(f"  snapshot list:    {len(rows)} outputs, {total:,} test BTGS")
    print("Private keys are in secret-keys.txt only (not printed). Back that file up somewhere safe.")

if __name__ == "__main__":
    main()
