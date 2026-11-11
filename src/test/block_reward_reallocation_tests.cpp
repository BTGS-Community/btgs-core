// Copyright (c) 2021-2025 The Dash Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <test/util/masternode.h>
#include <test/util/setup_common.h>

#include <bls/bls.h>
#include <evo/deterministicmns.h>
#include <masternode/payments.h>
#include <util/helpers.h>

#include <chainparams.h>
#include <deploymentstatus.h>
#include <node/miner.h>
#include <script/standard.h>
#include <validation.h>

#include <boost/test/unit_test.hpp>

using node::BlockAssembler;

struct TestChainBRRBeforeActivationSetup : public TestChainSetup
{
    // Force fast DIP3 activation
    TestChainBRRBeforeActivationSetup() :
        TestChainSetup(497, CBaseChainParams::REGTEST,
                       {"-dip3params=30:50", "-testactivationheight=brr@1000", "-testactivationheight=v20@1200", "-testactivationheight=mn_rr@2200"})
    {
    }
};

BOOST_AUTO_TEST_SUITE(block_reward_reallocation_tests)

BOOST_FIXTURE_TEST_CASE(simple_utxo_map_skips_unspendable_outputs, BasicTestingSetup) // BTGS: needs chain params
{
    CMutableTransaction tx;
    tx.vout.emplace_back(/*nValueIn=*/1, CScript() << OP_TRUE);
    tx.vout.emplace_back(/*nValueIn=*/0, CScript() << OP_RETURN);
    const auto tx_ref = MakeTransactionRef(tx);

    const auto utxos = BuildSimpleUtxoMap({tx_ref});

    BOOST_REQUIRE_EQUAL(utxos.size(), 1);
    BOOST_CHECK(utxos.contains(COutPoint{tx_ref->GetHash(), 0}));
}

// BTGS: test case block_reward_reallocation removed (Dash-only: treasury/superblocks or Dash reward reallocation)


BOOST_AUTO_TEST_SUITE_END()
