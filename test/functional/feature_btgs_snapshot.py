#!/usr/bin/env python3
# Copyright (c) 2026 The BTGS Community developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test the snapshot payout in block 1 (regtest with the built-in test list, -btgssnapshottest).

- block 1 pays the three test-list outputs (1 sat, 1000 BTGS, 250.5 BTGS) to the framework keys 2, 0 and 1
- snapshot coins are coinbase outputs: spending them before 100 confirmations is refused
- after maturity the same keys can spend them (this is what a holder does with a carried-over key)
- block 2 and later pay no snapshot outputs
"""
from decimal import Decimal

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import (
    assert_equal,
    assert_raises_rpc_error,
)

COIN = 100000000
# (framework key index, amount) - same hash160s as SNAPSHOT_REGTEST_TEST in src/btgs/snapshot_data.h
SNAPSHOT = [(0, Decimal("1000")), (1, Decimal("250.5")), (2, Decimal("0.00000001"))]
FEE = Decimal("0.01")


class BtgsSnapshotTest(BitcoinTestFramework):
    def set_test_params(self):
        self.num_nodes = 1
        self.setup_clean_chain = True
        self.extra_args = [["-btgssnapshottest"]]

    def run_test(self):
        node = self.nodes[0]
        keys = node.PRIV_KEYS
        miner = keys[5].address      # miner and spend target are other keys than the snapshot keys
        dest = keys[6].address
        spk = {i: node.validateaddress(keys[i].address)["scriptPubKey"] for i in range(8)}

        self.log.info("Mine block 1 and check that it pays the whole test list")
        block1_hash = self.generatetoaddress(node, 1, miner)[0]
        cb = node.getblock(block1_hash, 2)["tx"][0]
        paid = {(o["scriptPubKey"]["hex"], int(round(o["value"] * COIN))) for o in cb["vout"]}
        for idx, amount in SNAPSHOT:
            assert (spk[idx], int(amount * COIN)) in paid, f"snapshot output for key {idx} ({amount}) missing in block 1"
        total = sum(int(round(o["value"] * COIN)) for o in cb["vout"] if o["scriptPubKey"]["hex"] in (spk[0], spk[1], spk[2]))
        assert_equal(total, 125050000001)   # 1000 + 250.5 + 0.00000001 BTGS in satoshis
        self.log.info("Snapshot outputs are coinbase coins")
        outs = {}
        for idx, amount in SNAPSHOT:
            n = next(o["n"] for o in cb["vout"] if o["scriptPubKey"]["hex"] == spk[idx] and int(round(o["value"] * COIN)) == int(amount * COIN))
            outs[idx] = n
            utxo = node.gettxout(cb["txid"], n)
            assert utxo is not None and utxo["coinbase"]
            assert_equal(utxo["value"], amount)

        def signed_spend(idx, amount):
            raw = node.createrawtransaction([{"txid": cb["txid"], "vout": outs[idx]}], {dest: amount - FEE})
            prev = [{"txid": cb["txid"], "vout": outs[idx], "scriptPubKey": spk[idx], "amount": amount}]
            res = node.signrawtransactionwithkey(raw, [keys[idx].key], prev)
            assert res["complete"], res
            return res["hex"]

        self.log.info("Mine up to height 99: spending is still too early (100 confirmations needed)")
        self.generatetoaddress(node, 98, miner)
        assert_equal(node.getblockcount(), 99)
        assert_raises_rpc_error(-26, "bad-txns-premature-spend-of-coinbase", node.sendrawtransaction, signed_spend(0, SNAPSHOT[0][1]))

        self.log.info("Height 100: the snapshot coins can be spent with their keys")
        self.generatetoaddress(node, 1, miner)
        assert_equal(node.getblockcount(), 100)
        txids = {}
        for idx, amount in SNAPSHOT[:2]:
            txids[idx] = node.sendrawtransaction(signed_spend(idx, amount))
        self.generatetoaddress(node, 1, miner)
        for idx, amount in SNAPSHOT[:2]:
            assert node.gettxout(cb["txid"], outs[idx]) is None, "snapshot coin should be spent"
            new = node.gettxout(txids[idx], 0)
            assert new is not None
            assert_equal(new["value"], amount - FEE)
            assert_equal(new["confirmations"], 1)

        self.log.info("Block 2 and later pay no snapshot outputs")
        cb2 = node.getblock(node.getblockhash(2), 2)["tx"][0]
        scripts2 = {o["scriptPubKey"]["hex"] for o in cb2["vout"]}
        for idx in (0, 1, 2):
            assert spk[idx] not in scripts2


if __name__ == '__main__':
    BtgsSnapshotTest().main()
