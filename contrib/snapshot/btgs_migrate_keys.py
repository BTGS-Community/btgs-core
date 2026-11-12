#!/usr/bin/env python3
"""BTGS key migration - converts keys of the OLD BTGS chain to the NEW BTGS chain (same key, new format).

Run it OFFLINE on your own computer. It never sends anything anywhere and has no network code.
Your old keys control your snapshot balance on the new chain: same key -> new B... address.
Never paste, post or e-mail your keys or the output file. Delete the output file when you are done.

Inputs (use one or both):
  --wif FILE            one old private key (WIF) per line, or a 'dumpwallet' file (first word of each line is read)
  --descriptors FILE    the output of:  btgs-cli listdescriptors true   (saved to a file)
Optional:
  --snapshot FILE       the published btgs-snapshot-<height>.csv: shows the balance each key gets and keeps only keys in the list
  --range N             how many addresses to check per descriptor if the file does not say (default 1000)
  --gap N               extra addresses past the used range (default 200)
  --out FILE            where to write the new keys (default btgs-new-keys.txt)

Output: a table (old address -> new B... address, balance) and a file with the NEW private keys (WIF; start with P, or with 6 for very old uncompressed keys).
Import them into the new wallet with:  importprivkey <key> "" false   (then rescan once, after block 1 is mature).

Carried over: single-key addresses (legacy G..., SegWit bcg1q... 42 characters).
Not carried over automatically: P2SH (also sh(wpkh)), multisig, Taproot - these must be moved on the old chain first."""
import argparse, hashlib, hmac, json, os, re, sys

# ----- network constants -----
OLD_WIF, OLD_P2PKH, OLD_HRP = 176, 38, "bcg"      # old BTGS chain
NEW_WIF, NEW_P2PKH = 153, 25                       # new BTGS chain (P... keys, B... addresses)

# ----- secp256k1 (pure Python, Jacobian coordinates) -----
P = 2**256 - 2**32 - 977
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)

def _jdouble(p):
    x, y, z = p
    if y == 0: return (0, 1, 0)
    s = 4 * x * y * y % P; m = 3 * x * x % P
    nx = (m * m - 2 * s) % P
    return (nx, (m * (s - nx) - 8 * pow(y, 4, P)) % P, 2 * y * z % P)

def _jadd(p, q):
    if p[2] == 0: return q
    if q[2] == 0: return p
    z1s, z2s = p[2] * p[2] % P, q[2] * q[2] % P
    u1, u2 = p[0] * z2s % P, q[0] * z1s % P
    s1, s2 = p[1] * q[2] * z2s % P, q[1] * p[2] * z1s % P
    if u1 == u2: return _jdouble(p) if s1 == s2 else (0, 1, 0)
    h, r = (u2 - u1) % P, (s2 - s1) % P
    h2 = h * h % P; h3 = h * h2 % P; v = u1 * h2 % P
    nx = (r * r - h3 - 2 * v) % P
    return (nx, (r * (v - nx) - s1 * h3) % P, h * p[2] * q[2] % P)

def point_mul(k, pt=G):
    r, a = (0, 1, 0), (pt[0], pt[1], 1)
    while k:
        if k & 1: r = _jadd(r, a)
        a = _jdouble(a); k >>= 1
    if r[2] == 0: raise ValueError("point at infinity")
    zi = pow(r[2], P - 2, P)
    return (r[0] * zi * zi % P, r[1] * zi * zi * zi % P)

def pubkey(k, compressed=True):
    x, y = point_mul(k)
    if compressed: return bytes([2 + (y & 1)]) + x.to_bytes(32, "big")
    return b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")

# ----- hashing / base58 / bech32 -----
def _ripemd160(data):
    try: return hashlib.new("ripemd160", data).digest()
    except ValueError: return _ripemd160_py(data)

def _ripemd160_py(data):
    ML = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,7,4,13,1,10,6,15,3,12,0,9,5,2,14,11,8,3,10,14,4,9,15,8,1,2,7,0,6,13,11,5,12,1,9,11,10,0,8,12,4,13,3,7,15,14,5,6,2,4,0,5,9,7,12,2,10,14,1,3,8,11,6,15,13]
    MR = [5,14,7,0,9,2,11,4,13,6,15,8,1,10,3,12,6,11,3,7,0,13,5,10,14,15,8,12,4,9,1,2,15,5,1,3,7,14,6,9,11,8,12,2,10,0,4,13,8,6,4,1,3,11,15,0,5,12,2,13,9,7,10,14,12,15,10,4,1,5,8,7,6,2,13,14,0,3,9,11]
    RL = [11,14,15,12,5,8,7,9,11,13,14,15,6,7,9,8,7,6,8,13,11,9,7,15,7,12,15,9,11,7,13,12,11,13,6,7,14,9,13,15,14,8,13,6,5,12,7,5,11,12,14,15,14,15,9,8,9,14,5,6,8,6,5,12,9,15,5,11,6,8,13,12,5,12,13,14,11,8,5,6]
    RR = [8,9,9,11,13,15,15,5,7,7,8,11,14,14,12,6,9,13,15,7,12,8,9,11,7,7,12,7,6,15,13,11,9,7,15,11,8,6,6,14,12,13,5,14,13,13,7,5,15,5,8,11,14,14,6,14,6,9,12,9,12,5,15,8,8,5,12,9,12,5,14,6,8,13,6,5,15,13,11,11]
    KL = [0, 0x5a827999, 0x6ed9eba1, 0x8f1bbcdc, 0xa953fd4e]
    KR = [0x50a28be6, 0x5c4dd124, 0x6d703ef3, 0x7a6d76e9, 0]
    def fi(x, y, z, i): return (x ^ y ^ z, (x & y) | (~x & z), (x | ~y) ^ z, (x & z) | (y & ~z), x ^ (y | ~z))[i]
    def rol(x, i): return ((x << i) | ((x & 0xffffffff) >> (32 - i))) & 0xffffffff
    def compress(h0, h1, h2, h3, h4, block):
        al, bl, cl, dl, el = h0, h1, h2, h3, h4; ar, br, cr, dr, er = h0, h1, h2, h3, h4
        x = [int.from_bytes(block[4*i:4*(i+1)], "little") for i in range(16)]
        for j in range(80):
            rnd = j >> 4
            al = rol(al + fi(bl, cl, dl, rnd) + x[ML[j]] + KL[rnd], RL[j]) + el
            al, bl, cl, dl, el = el, al, bl, rol(cl, 10), dl
            ar = rol(ar + fi(br, cr, dr, 4 - rnd) + x[MR[j]] + KR[rnd], RR[j]) + er
            ar, br, cr, dr, er = er, ar, br, rol(cr, 10), dr
        return h1 + cl + dr, h2 + dl + er, h3 + el + ar, h4 + al + br, h0 + bl + cr
    state = (0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476, 0xc3d2e1f0)
    for b in range(len(data) >> 6): state = compress(*state, data[64*b:64*(b+1)])
    pad = b"\x80" + b"\x00" * ((119 - len(data)) & 63)
    fin = data[len(data) & ~63:] + pad + (8 * len(data)).to_bytes(8, "little")
    for b in range(len(fin) >> 6): state = compress(*state, fin[64*b:64*(b+1)])
    return b"".join((h & 0xffffffff).to_bytes(4, "little") for h in state)

def hash160(b): return _ripemd160(hashlib.sha256(b).digest())
def dsha(b): return hashlib.sha256(hashlib.sha256(b).digest()).digest()
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def b58check(payload):
    data = payload + dsha(payload)[:4]; n = int.from_bytes(data, "big"); out = ""
    while n: n, r = divmod(n, 58); out = B58[r] + out
    return "1" * (len(data) - len(data.lstrip(b"\0"))) + out

def b58decode_check(s):
    n = 0
    for c in s:
        if c not in B58: raise ValueError("not a base58 string")
        n = n * 58 + B58.index(c)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    raw = b"\0" * (len(s) - len(s.lstrip("1"))) + raw
    if len(raw) < 5 or dsha(raw[:-4])[:4] != raw[-4:]: raise ValueError("bad checksum")
    return raw[:-4]

CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
def _polymod(values):
    gen = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]; chk = 1
    for v in values:
        top = chk >> 25; chk = (chk & 0x1ffffff) << 5 ^ v
        for i in range(5): chk ^= gen[i] if (top >> i) & 1 else 0
    return chk
def bech32_p2wpkh(hrp, h160):
    conv = []; acc = 0; bits = 0
    for byte in h160:
        acc = (acc << 8) | byte; bits += 8
        while bits >= 5: bits -= 5; conv.append((acc >> bits) & 31)
    if bits: conv.append((acc << (5 - bits)) & 31)
    data = [0] + conv
    exp = [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]
    pm = _polymod(exp + data + [0] * 6) ^ 1
    return hrp + "1" + "".join(CHARSET[d] for d in data + [(pm >> 5 * (5 - i)) & 31 for i in range(6)])

# ----- key formats -----
def parse_wif(s, version):
    raw = b58decode_check(s)
    if raw[0] != version: raise ValueError("not an old-chain private key")
    body = raw[1:]
    if len(body) == 33 and body[32] == 1: return int.from_bytes(body[:32], "big"), True
    if len(body) == 32: return int.from_bytes(body, "big"), False
    raise ValueError("bad private key length")

def make_wif(k, compressed, version):
    return b58check(bytes([version]) + k.to_bytes(32, "big") + (b"\x01" if compressed else b""))

def addresses(k, compressed):
    h = hash160(pubkey(k, compressed))
    old = [b58check(bytes([OLD_P2PKH]) + h)] + ([bech32_p2wpkh(OLD_HRP, h)] if compressed else [])
    return h, old, b58check(bytes([NEW_P2PKH]) + h)

# ----- BIP32 (private derivation only) -----
def bip32_decode(xprv):
    raw = b58decode_check(xprv)
    if len(raw) != 78 or raw[45] != 0: raise ValueError("not an extended PRIVATE key (use: listdescriptors true)")
    return int.from_bytes(raw[46:78], "big"), raw[13:45]     # key, chain code

def ckd(k, c, i):
    data = (b"\x00" + k.to_bytes(32, "big") if i >= 0x80000000 else pubkey(k)) + i.to_bytes(4, "big")
    I = hmac.new(c, data, hashlib.sha512).digest()
    il = int.from_bytes(I[:32], "big")
    if il >= N: raise ValueError("invalid child")
    return (il + k) % N, I[32:]

DESC_RE = re.compile(r"^(pkh|wpkh|sh\(wpkh|tr|sh|wsh|combo)\(\s*(\[[^\]]*\])?([1-9A-HJ-NP-Za-km-z]{100,120})((?:/[0-9]+[h']?)*)(/\*[h']?)?")
def keys_from_descriptor(desc, rng, gap):
    desc = desc.split("#")[0]; m = DESC_RE.match(desc)
    if not m: return None, "unsupported descriptor"
    kind = m.group(1)
    if kind not in ("pkh", "wpkh"):
        return None, f"{kind}(...) is not a single-key address type - those coins must be moved on the old chain first"
    k, c = bip32_decode(m.group(3))
    for step in [x for x in m.group(4).split("/") if x]:
        hard = step[-1] in "h'"; idx = int(step.rstrip("h'")); k, c = ckd(k, c, idx + (0x80000000 if hard else 0))
    out = []
    if m.group(5):
        for i in range(0, rng + gap + 1):
            kk, _ = ckd(k, c, i); out.append(kk)
    else:
        out.append(k)
    return out, kind

# ----- snapshot list -----
def load_snapshot(path):
    d = {}
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"): continue
        parts = line.split(",")
        d[parts[2]] = (int(parts[1]), parts[0])
    return d

def fmt(sats): return f"{sats / 1e8:,.8f}".rstrip("0").rstrip(".")

def selftest():
    k = 1
    assert pubkey(k).hex() == "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
    assert hash160(pubkey(k)).hex() == "751e76e8199196d454941c45d1b3a323f1433bd6"
    assert hash160(b"").hex() == "b472a266d0bd89c13706a4132ccfb16f7c3b9fcb"
    assert _ripemd160_py(b"abc").hex() == "8eb208f7e05d987a9b044a8e98c6b087f15a0bfc"
    assert bech32_p2wpkh("bc", bytes.fromhex("751e76e8199196d454941c45d1b3a323f1433bd6")) == "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
    w = make_wif(k, True, OLD_WIF); assert parse_wif(w, OLD_WIF) == (k, True)
    print("selftest OK")

def main():
    ap = argparse.ArgumentParser(description="Convert old-chain BTGS keys to the new chain")
    ap.add_argument("--wif"); ap.add_argument("--descriptors"); ap.add_argument("--snapshot")
    ap.add_argument("--range", type=int, default=1000); ap.add_argument("--gap", type=int, default=200)
    ap.add_argument("--out", default="btgs-new-keys.txt"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest: return selftest()
    if not a.wif and not a.descriptors: ap.error("give --wif and/or --descriptors")
    snap = load_snapshot(a.snapshot) if a.snapshot else None
    keys = []                                                   # (k, compressed, source)
    if a.wif:
        for line in open(a.wif):
            w = line.strip().split()[0] if line.strip() and not line.startswith("#") else ""
            if not w: continue
            try: k, comp = parse_wif(w, OLD_WIF); keys.append((k, comp, "wif"))
            except Exception: pass
    if a.descriptors:
        data = json.load(open(a.descriptors))
        for d in data.get("descriptors", []):
            r = d.get("range"); rng = (r[1] if isinstance(r, list) else r) if r else a.range
            ks, info = keys_from_descriptor(d["desc"], rng or a.range, a.gap)
            if ks is None: print("skipped:", info); continue
            keys += [(k, True, info) for k in ks]
    seen = set(); rows = []
    for k, comp, src in keys:
        h, old, new = addresses(k, comp)
        if h in seen: continue
        seen.add(h)
        if snap is not None:
            if h.hex() not in snap: continue
            if snap[h.hex()][1] != new: print("WARNING: list address differs from computed address for", new)
            amt = snap[h.hex()][0]
        else: amt = None
        rows.append((old, new, amt, make_wif(k, comp, NEW_WIF)))
    if not rows: print("No keys that are in the snapshot list were found."); return
    print(f"{'OLD ADDRESS(ES)':<60} {'NEW ADDRESS':<36} BALANCE"); print("-" * 110)
    total = 0
    for old, new, amt, wif in rows:
        print(f"{' / '.join(old):<60} {new:<36} {fmt(amt) if amt is not None else '(no list given)'}")
        total += amt or 0
    if snap is not None: print("-" * 110, f"\n{len(rows)} addresses, {fmt(total)} BTGS will be yours on the new chain")
    fd = os.open(a.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("# NEW BTGS private keys - SECRET. Import with: importprivkey <key> \"\" false\n# Delete this file when you are done.\n")
        for old, new, amt, wif in rows: f.write(f"{wif}  # {new}" + (f"  {fmt(amt)} BTGS" if amt is not None else "") + "\n")
    print(f"\nNew private keys written to {a.out} (keep it secret, delete it when done)")

if __name__ == "__main__":
    main()
