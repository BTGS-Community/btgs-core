#!/usr/bin/env python3
# Copyright (c) 2018-2025 The Dash Core developers
# Copyright (c) 2026 The BTGS Community developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""BTGS governance.

BTGS keeps BTGS's governance system (proposals, votes, masternode voting),
but the treasury share of the block reward is 0. So:
- the superblock budget is 0 before and after v20,
- proposals can still be prepared, submitted and voted on,
- no superblock trigger is ever created, and superblocks pay no proposals.
"""

from test_framework.messages import uint256_to_string
from test_framework.test_framework import DashTestFramework
from test_framework.governance import prepare_object
from test_framework.util import assert_equal, satoshi_round


class BTGSGovernanceTest(DashTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.set_dash_test_params(6, 5, [[
            "-budgetparams=10:10:10",
        ]] * 6)
        self.delay_v20_and_mn_rr(height=160)

    def check_superblockbudget(self):
        # BTGS: no treasury, before and after v20 (v20 activates at 160)
        for height in (120, 140, 160, 180, 200, 220):
            assert_equal(self.nodes[0].getsuperblockbudget(height), 0)

    def check_no_triggers(self):
        for node in self.nodes:
            assert_equal(len(node.gobject("list", "valid", "triggers")), 0)

    def check_superblock_pays_no_proposal(self, height):
        coinbase = self.nodes[0].getblock(self.nodes[0].getblockhash(height), 2)["tx"][0]
        paid_to = [txout["scriptPubKey"].get("address") for txout in coinbase["vout"]]
        for address in (self.p0_payout_address, self.p1_payout_address, self.p2_payout_address):
            assert address not in paid_to, f"superblock {height} paid proposal address {address}"

    def run_test(self):
        sb_cycle = 20

        self.log.info("Governance parameters: budget is 0 (no treasury)")
        governance_info = self.nodes[0].getgovernanceinfo()
        assert_equal(governance_info['governanceminquorum'], 1)
        assert_equal(governance_info['proposalfee'], 1)
        assert_equal(governance_info['superblockcycle'], sb_cycle)
        assert_equal(governance_info['superblockmaturitywindow'], 10)
        assert_equal(governance_info['nextsuperblock'], governance_info['lastsuperblock'] + sb_cycle)
        assert_equal(governance_info['governancebudget'], 0)
        self.check_superblockbudget()

        self.nodes[0].sporkupdate("SPORK_2_INSTANTSEND_ENABLED", 4070908800)
        self.wait_for_sporks_same()
        assert_equal(len(self.nodes[0].gobject("list-prepared")), 0)

        self.log.info("Prepare proposals")
        proposal_time = self.mocktime
        self.p0_payout_address = self.nodes[0].getnewaddress()
        self.p1_payout_address = self.nodes[0].getnewaddress()
        self.p2_payout_address = self.nodes[0].getnewaddress()
        amounts = [satoshi_round("1.1"), satoshi_round("3.3"), satoshi_round("5")]
        addresses = [self.p0_payout_address, self.p1_payout_address, self.p2_payout_address]
        prepared = [prepare_object(self.nodes[0], 1, uint256_to_string(0), proposal_time, 1, f"Proposal_{i}", amounts[i], addresses[i])
                    for i in range(3)]

        self.bump_mocktime(6)
        self.generate(self.nodes[0], 6, sync_fun=self.sync_blocks())
        assert_equal(len(self.nodes[0].gobject("list-prepared")), 3)
        assert_equal(len(self.nodes[0].gobject("list")), 0)

        self.log.info("Submit proposals")
        hashes = [self.nodes[0].gobject("submit", "0", 1, proposal_time, p["hex"], p["collateralHash"]) for p in prepared]
        assert_equal(len(self.nodes[0].gobject("list")), 3)
        self.wait_until(lambda: len(self.nodes[1].gobject("list")) == 3, timeout=5)

        self.log.info("Cast votes: all masternodes vote yes on every proposal")
        for h in hashes:
            self.nodes[0].gobject("vote-many", h, "funding", "yes")
            assert_equal(self.nodes[0].gobject("get", h)["FundingResult"]["YesCount"], self.mn_count)
            assert_equal(self.nodes[0].gobject("get", h)["FundingResult"]["NoCount"], 0)
            self.wait_until(lambda h=h: self.nodes[1].gobject("get", h)["FundingResult"]["YesCount"] == self.mn_count, timeout=5)
        assert_equal(self.nodes[0].gobject("count")["votes"], 3 * self.mn_count)
        self.check_no_triggers()

        self.log.info("Mine through two full superblock cycles (across v20 at 160): no trigger, no payment")
        start = self.nodes[0].getblockcount()
        end = (start // sb_cycle + 3) * sb_cycle
        for _ in range(end - start):
            self.bump_mocktime(1)
            self.generate(self.nodes[0], 1, sync_fun=self.sync_blocks())
            self.check_no_triggers()
        assert self.nodes[0].getblockcount() >= 160
        assert_equal(self.nodes[0].getdeploymentinfo()["deployments"]["v20"]["active"], True)
        self.check_superblockbudget()

        for height in range((start // sb_cycle + 1) * sb_cycle, end + 1, sb_cycle):
            self.check_superblock_pays_no_proposal(height)

        self.log.info("Proposals and votes are still there")
        assert_equal(len(self.nodes[0].gobject("list")), 3)
        for h in hashes:
            assert_equal(self.nodes[0].gobject("get", h)["FundingResult"]["YesCount"], self.mn_count)


if __name__ == '__main__':
    BTGSGovernanceTest().main()
