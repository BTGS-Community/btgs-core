#!/usr/bin/env python3
# Copyright (c) 2024-2025 The Dash Core developers
# Copyright (c) 2026 The BTGS Community developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""BTGS: a node that missed proposals and votes still syncs superblocks covered by a ChainLock.

BTGS has no treasury (superblock budget 0), so no trigger is ever created. A node isolated
while proposals are voted on must still accept the superblock heights once it reconnects."""
import json

from test_framework.messages import uint256_to_string
from test_framework.test_framework import DashTestFramework
from test_framework.util import assert_equal, satoshi_round


class BTGSGovernanceChainLockTest(DashTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.set_dash_test_params(6, 5, [["-budgetparams=10:10:10"]] * 6)

    def prepare_object(self, object_type, parent_hash, creation_time, revision, name, amount, payment_address):
        proposal_time = int(creation_time)
        proposal_template = {
            "type": object_type,
            "name": name,
            "start_epoch": proposal_time,
            "end_epoch": proposal_time + 20 * 156,
            "payment_amount": float(amount),
            "payment_address": payment_address,
            "url": "https://dash.org"
        }
        proposal_hex = ''.join(format(x, '02x') for x in json.dumps(proposal_template).encode())
        collateral_hash = self.nodes[0].gobject("prepare", parent_hash, revision, proposal_time, proposal_hex)
        return {"collateralHash": collateral_hash, "hex": proposal_hex}

    def check_no_triggers(self, nodes):
        for node in nodes:
            assert_equal(len(node.gobject("list", "valid", "triggers")), 0)

    def run_test(self):
        sb_cycle = 20

        self.log.info("Make sure ChainLocks are active")
        self.nodes[0].sporkupdate("SPORK_17_QUORUM_DKG_ENABLED", 0)
        self.wait_for_sporks_same()
        self.mine_quorum()
        self.sync_blocks()
        self.wait_for_chainlocked_block_all_nodes(self.nodes[0].getbestblockhash())

        # Move to the superblock cycle start block
        n = sb_cycle - self.nodes[0].getblockcount() % sb_cycle
        if n > 0:
            self.bump_mocktime(156 * n)
            self.generate(self.nodes[0], n, sync_fun=lambda: self.sync_blocks())

        self.log.info("Prepare proposals")
        proposal_time = self.mocktime
        p0 = self.prepare_object(1, uint256_to_string(0), proposal_time, 1, "Proposal_0", satoshi_round("1.1"), self.nodes[0].getnewaddress())
        p1 = self.prepare_object(1, uint256_to_string(0), proposal_time, 1, "Proposal_1", satoshi_round("3.3"), self.nodes[0].getnewaddress())
        self.bump_mocktime(60 * 10 + 1)
        self.generate(self.nodes[0], 6, sync_fun=self.sync_blocks())
        assert_equal(len(self.nodes[0].gobject("list-prepared")), 2)

        self.log.info("Submit proposals")
        p0_hash = self.nodes[0].gobject("submit", "0", 1, proposal_time, p0["hex"], p0["collateralHash"])
        p1_hash = self.nodes[0].gobject("submit", "0", 1, proposal_time, p1["hex"], p1["collateralHash"])
        assert_equal(len(self.nodes[0].gobject("list")), 2)

        self.log.info("Isolate a node so that it misses the votes")
        self.isolate_node(5)

        self.log.info("Vote proposals")
        self.nodes[0].gobject("vote-many", p0_hash, "funding", "yes")
        self.nodes[0].gobject("vote-many", p1_hash, "funding", "yes")
        assert_equal(self.nodes[0].gobject("get", p0_hash)["FundingResult"]["YesCount"], self.mn_count)
        assert_equal(self.nodes[0].gobject("get", p1_hash)["FundingResult"]["YesCount"], self.mn_count)

        self.log.info("Mine through the maturity window, the superblock and one more cycle: no trigger (budget 0)")
        sb_block_height = self.nodes[0].getblockcount() // sb_cycle * sb_cycle + sb_cycle
        target = sb_block_height + sb_cycle + 1
        while self.nodes[0].getblockcount() < target:
            self.bump_mocktime(156)
            self.generate(self.nodes[0], 1, sync_fun=lambda: self.sync_blocks(self.nodes[0:5]))
            self.check_no_triggers(self.nodes[0:5])
        self.wait_for_chainlocked_block(self.nodes[0], self.nodes[0].getbestblockhash())

        self.log.info("Reconnect the isolated node: it syncs past both superblock heights")
        self.reconnect_isolated_node(5, 0)
        # NOTE: bumping mocktime too much after recent reconnect can result in "timeout downloading block"
        self.bump_mocktime(1)
        self.generate(self.nodes[0], 1, sync_fun=self.sync_blocks())
        assert_equal(self.nodes[5].getbestblockhash(), self.nodes[0].getbestblockhash())
        self.check_no_triggers(self.nodes)


if __name__ == '__main__':
    BTGSGovernanceChainLockTest().main()
