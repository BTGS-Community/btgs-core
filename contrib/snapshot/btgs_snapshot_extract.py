#!/usr/bin/env python3
"""BTGS snapshot extract (read-only) - runs against a node of the OLD BTGS chain.

Reads blocks 1..HEIGHT, builds the coin set at that height, and writes the carry-over list for the
new chain: one line per new B-address (same key as the old address) with its balance in satoshis.

  carries over (same key):  bcg1q... 42 chars (P2WPKH), legacy G... (P2PKH), old-style pay-to-pubkey
  must be moved first:      bcg1q... 62 chars (P2WSH), bcg1p... (Taproot), P2SH, other scripts
  genesis (block 0) coins can never be spent and are skipped; addresses in --exclude stay out.

Only uses RPC getblockhash / getblock. Changes nothing on the node.

Usage:  python3 btgs_snapshot_extract.py --height 17600 [--exclude exclude.txt] [--port 18881] [--datadir ~/.btgs]
Writes: btgs-snapshot-<height>.csv  and  btgs-snapshot-<height>-summary.txt"""
import argparse, base64, hashlib, json, os, time, urllib.request
from collections import defaultdict
from decimal import Decimal

# ---------- RPC ----------
class RPC:
    def __init__(self, port, datadir):
        cookie = os.path.join(datadir, ".cookie")
        if os.path.exists(cookie):
            auth = open(cookie).read().strip()
        else:
            u, p = os.environ.get("BTGS_RPCUSER"), os.environ.get("BTGS_RPCPASSWORD")
            conf = os.path.join(datadir, "btgs.conf")
            if (not u or not p) and os.path.exists(conf):
                for line in open(conf):
                    k, _, v = line.strip().partition("=")
                    if k == "rpcuser" and not u: u = v
                    if k == "rpcpassword" and not p: p = v
            if not u or not p:
                raise SystemExit("No .cookie and no rpcuser/rpcpassword found")
            auth = f"{u}:{p}"
        self.url = f"http://127.0.0.1:{port}/"
        self.hdr = {"Authorization": "Basic " + base64.b64encode(auth.encode()).decode(), "Content-Type": "application/json"}
        self.n = 0
    def __call__(self, method, *params):
        self.n += 1
        body = json.dumps({"jsonrpc": "1.0", "id": self.n, "method": method, "params": list(params)}).encode()
        with urllib.request.urlopen(urllib.request.Request(self.url, body, self.hdr), timeout=300) as r:
            res = json.loads(r.read(), parse_float=Decimal)
        if res.get("error"):
            raise RuntimeError(f"{method}: {res['error']}")
        return res["result"]

# ---------- hashing / addresses ----------
def _ripemd160(data):
    try:
        return hashlib.new("ripemd160", data).digest()
    except ValueError:  # OpenSSL 3 without the legacy provider: pure Python fallback
        return _ripemd160_py(data)

def _ripemd160_py(data):
    # pure Python RIPEMD-160 (same algorithm as Bitcoin Core's test framework ripemd160.py)
    ML = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,7,4,13,1,10,6,15,3,12,0,9,5,2,14,11,8,3,10,14,4,9,15,8,1,2,7,0,6,13,11,5,12,1,9,11,10,0,8,12,4,13,3,7,15,14,5,6,2,4,0,5,9,7,12,2,10,14,1,3,8,11,6,15,13]
    MR = [5,14,7,0,9,2,11,4,13,6,15,8,1,10,3,12,6,11,3,7,0,13,5,10,14,15,8,12,4,9,1,2,15,5,1,3,7,14,6,9,11,8,12,2,10,0,4,13,8,6,4,1,3,11,15,0,5,12,2,13,9,7,10,14,12,15,10,4,1,5,8,7,6,2,13,14,0,3,9,11]
    RL = [11,14,15,12,5,8,7,9,11,13,14,15,6,7,9,8,7,6,8,13,11,9,7,15,7,12,15,9,11,7,13,12,11,13,6,7,14,9,13,15,14,8,13,6,5,12,7,5,11,12,14,15,14,15,9,8,9,14,5,6,8,6,5,12,9,15,5,11,6,8,13,12,5,12,13,14,11,8,5,6]
    RR = [8,9,9,11,13,15,15,5,7,7,8,11,14,14,12,6,9,13,15,7,12,8,9,11,7,7,12,7,6,15,13,11,9,7,15,11,8,6,6,14,12,13,5,14,13,13,7,5,15,5,8,11,14,14,6,14,6,9,12,9,12,5,15,8,8,5,12,9,12,5,14,6,8,13,6,5,15,13,11,11]
    KL = [0, 0x5a827999, 0x6ed9eba1, 0x8f1bbcdc, 0xa953fd4e]
    KR = [0x50a28be6, 0x5c4dd124, 0x6d703ef3, 0x7a6d76e9, 0]
    def fi(x, y, z, i):
        return (x ^ y ^ z, (x & y) | (~x & z), (x | ~y) ^ z, (x & z) | (y & ~z), x ^ (y | ~z))[i]
    def rol(x, i):
        return ((x << i) | ((x & 0xffffffff) >> (32 - i))) & 0xffffffff
    def compress(h0, h1, h2, h3, h4, block):
        al, bl, cl, dl, el = h0, h1, h2, h3, h4
        ar, br, cr, dr, er = h0, h1, h2, h3, h4
        x = [int.from_bytes(block[4*i:4*(i+1)], "little") for i in range(16)]
        for j in range(80):
            rnd = j >> 4
            al = rol(al + fi(bl, cl, dl, rnd) + x[ML[j]] + KL[rnd], RL[j]) + el
            al, bl, cl, dl, el = el, al, bl, rol(cl, 10), dl
            ar = rol(ar + fi(br, cr, dr, 4 - rnd) + x[MR[j]] + KR[rnd], RR[j]) + er
            ar, br, cr, dr, er = er, ar, br, rol(cr, 10), dr
        return h1 + cl + dr, h2 + dl + er, h3 + el + ar, h4 + al + br, h0 + bl + cr
    state = (0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476, 0xc3d2e1f0)
    for b in range(len(data) >> 6):
        state = compress(*state, data[64*b:64*(b+1)])
    pad = b"\x80" + b"\x00" * ((119 - len(data)) & 63)
    fin = data[len(data) & ~63:] + pad + (8 * len(data)).to_bytes(8, "little")
    for b in range(len(fin) >> 6):
        state = compress(*state, fin[64*b:64*(b+1)])
    return b"".join((h & 0xffffffff).to_bytes(4, "little") for h in state)

def hash160(b): return _ripemd160(hashlib.sha256(b).digest())
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
def b58check(payload):
    data = payload + hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    n = int.from_bytes(data, "big"); out = ""
    while n: n, r = divmod(n, 58); out = B58[r] + out
    return "1" * (len(data) - len(data.lstrip(b"\0"))) + out
BTGS_P2PKH = 25  # new chain: B...
def new_address(h160): return b58check(bytes([BTGS_P2PKH]) + h160)

def carry_key(spk_hex):
    """hash160 for outputs that carry over to the same key, else None"""
    s = bytes.fromhex(spk_hex)
    if len(s) == 22 and s[0] == 0x00 and s[1] == 0x14:                                   # P2WPKH bcg1q (42)
        return s[2:22]
    if len(s) == 25 and s[:3] == b"\x76\xa9\x14" and s[23:] == b"\x88\xac":             # P2PKH G...
        return s[3:23]
    if (len(s) == 35 and s[0] == 33 and s[34] == 0xac) or (len(s) == 67 and s[0] == 65 and s[66] == 0xac):  # P2PK
        return hash160(s[1:-1])
    return None

def fmt(sats):
    return f"{Decimal(sats) / Decimal(10**8):,.8f}".rstrip("0").rstrip(".")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--height", type=int, required=True, help="snapshot height on the old chain")
    ap.add_argument("--exclude", default="", help="file with old addresses that stay out (one per line, # comments)")
    ap.add_argument("--port", type=int, default=18881)
    ap.add_argument("--datadir", default=os.path.expanduser("~/.btgs"))
    a = ap.parse_args()
    rpc = RPC(a.port, a.datadir)
    tip = rpc("getblockcount")
    if a.height > tip: raise SystemExit(f"Height {a.height} is above the node's tip {tip}")
    if tip - a.height < 10: print(f"WARNING: snapshot height is only {tip - a.height} blocks below the tip (reorg risk)")
    excluded = set()
    if a.exclude:
        for line in open(a.exclude):
            line = line.split("#", 1)[0].strip()
            if line: excluded.add(line)

    print(f"Reading blocks 1-{a.height} (read-only, genesis skipped)...")
    utxo = {}; t0 = time.time()
    for h in range(1, a.height + 1):
        blk = rpc("getblock", rpc("getblockhash", h), 2)
        for tx in blk["tx"]:
            for v in tx["vin"]:
                if "coinbase" not in v: utxo.pop((v["txid"], v["vout"]), None)
            for vo in tx["vout"]:
                sats = int(Decimal(str(vo["value"])) * 10**8)
                if sats == 0: continue
                spk = vo["scriptPubKey"]
                utxo[(tx["txid"], vo["n"])] = (sats, spk["hex"], spk.get("address") or f"{spk.get('type', '?')}:{spk['hex'][:40]}", spk.get("type", "?"), h)
        if h % 2000 == 0 or h == a.height:
            print(f"  read {h}/{a.height} ({time.time()-t0:.0f}s)", flush=True)

    carry = defaultdict(int); old_of = defaultdict(set)
    must_move = defaultdict(lambda: [0, "", 0]); excl = defaultdict(int)
    for sats, spk_hex, old, typ, h in utxo.values():
        if old in excluded:
            excl[old] += sats; continue
        k = carry_key(spk_hex)
        if k is None:
            mm = must_move[old]; mm[0] += sats; mm[1] = typ; mm[2] += 1
        else:
            carry[k] += sats; old_of[k].add(old)

    rows = sorted(carry.items(), key=lambda kv: kv[0].hex())   # deterministic order: by key hash
    out = f"btgs-snapshot-{a.height}.csv"
    with open(out, "w") as f:
        f.write("# new_address,amount_sats,hash160,old_addresses\n")
        for k, sats in rows:
            f.write(f"{new_address(k)},{sats},{k.hex()},{';'.join(sorted(old_of[k]))}\n")
    list_hash = hashlib.sha256("".join(f"{k.hex()},{s}\n" for k, s in rows).encode()).hexdigest()

    total = sum(s for _, s in rows); n = len(rows)
    L = [f"BTGS SNAPSHOT EXTRACT (read-only) - old chain height {a.height} (tip {tip})", "=" * 76,
         f"Carry over:  {n} new addresses, {fmt(total)} BTGS  -> {out}",
         f"List fingerprint (sha256 of hash160,amount lines): {list_hash}",
         f"Block 1 size estimate: {n * 34:,} bytes of outputs, {n} sigops (limits: ~2,000,000 bytes, 40,000 sigops)"]
    if n * 34 > 1_900_000 or n > 39_000:
        L.append("WARNING: too many outputs for one block - the list must be split over more blocks")
    L += ["", f"Excluded (--exclude): {len(excl)} addresses, {fmt(sum(excl.values()))} BTGS"]
    L += [f"  {fmt(s):>18s}  {ad}" for ad, s in sorted(excl.items(), key=lambda kv: -kv[1])]
    L += ["", f"MUST BE MOVED FIRST (not carried over): {len(must_move)} addresses, {fmt(sum(v[0] for v in must_move.values()))} BTGS"]
    L += [f"  {fmt(v[0]):>18s}  {v[1]:24s} {ad}  ({v[2]} coins)" for ad, v in sorted(must_move.items(), key=lambda kv: -kv[1][0])]
    report = "\n".join(L)
    open(f"btgs-snapshot-{a.height}-summary.txt", "w").write(report + "\n")
    print("\n" + report + f"\nSaved: {out} and btgs-snapshot-{a.height}-summary.txt")

if __name__ == "__main__":
    main()
