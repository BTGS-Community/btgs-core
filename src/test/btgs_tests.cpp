// Copyright (c) 2026 The BTGS Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

// BTGS: checks of the real mainnet values (the rest of the test suite runs on regtest,
// which keeps Dash's test amounts: 500 reward, 1,000 collateral)

#include <chainparams.h>
#include <consensus/amount.h>
#include <evo/dmn_types.h>
#include <key_io.h>
#include <masternode/payments.h>
#include <script/standard.h>
#include <test/util/setup_common.h>
#include <validation.h>

#include <boost/test/unit_test.hpp>

BOOST_FIXTURE_TEST_SUITE(btgs_tests, BasicTestingSetup) // mainnet params

BOOST_AUTO_TEST_CASE(btgs_network)
{
    const CChainParams& params = Params();
    BOOST_CHECK_EQUAL(params.NetworkIDString(), CBaseChainParams::MAIN);
    BOOST_CHECK_EQUAL(params.GetConsensus().nPowTargetSpacing, 200);
    BOOST_CHECK_EQUAL(params.GetDefaultPort(), 19888);
    const auto& magic = params.MessageStart();
    BOOST_CHECK(magic[0] == 0xce && magic[1] == 0x99 && magic[2] == 0xa8 && magic[3] == 0xd1);
    // normal addresses start with B, multisig/script addresses with M
    BOOST_CHECK_EQUAL(EncodeDestination(PKHash(uint160())).front(), 'B');
    BOOST_CHECK_EQUAL(EncodeDestination(ScriptHash(uint160())).front(), 'M');
}

BOOST_AUTO_TEST_CASE(btgs_block_reward)
{
    const auto& consensus = Params().GetConsensus();
    BOOST_CHECK_EQUAL(consensus.nSubsidyHalvingInterval, 157680);
    // 12 BTGS for the first year, then cut by 1/14 every 157,680 blocks
    BOOST_CHECK_EQUAL(GetBlockSubsidyInner(0, 0, consensus, true), 12 * COIN);
    BOOST_CHECK_EQUAL(GetBlockSubsidyInner(0, 157679, consensus, true), 12 * COIN);
    BOOST_CHECK_EQUAL(GetBlockSubsidyInner(0, 157680, consensus, true), 12 * COIN - 12 * COIN / 14);
    // no treasury (superblock) part
    BOOST_CHECK_EQUAL(GetSuperblockSubsidyInner(0, 1000, consensus, true), 0);

    // total mined supply stays below ~26.5M and below MAX_MONEY
    CAmount total{0};
    for (int year = 0; year < 400; ++year) {
        total += GetBlockSubsidyInner(0, year * 157680, consensus, true) * 157680;
    }
    BOOST_CHECK(total > 26400000 * COIN && total < 26500000 * COIN);
    BOOST_CHECK(MoneyRange(total));
}

BOOST_AUTO_TEST_CASE(btgs_dev_fund_and_split)
{
    // 25% at launch, -1 point every 6,048 blocks, 5% floor
    BOOST_CHECK_EQUAL(GetDevFundPayment(0, 12 * COIN), 0);
    BOOST_CHECK_EQUAL(GetDevFundPayment(1, 12 * COIN), 3 * COIN);
    BOOST_CHECK_EQUAL(GetDevFundPayment(6048, 12 * COIN), 3 * COIN);
    BOOST_CHECK_EQUAL(GetDevFundPayment(6049, 12 * COIN), 12 * COIN * 24 / 100);
    BOOST_CHECK_EQUAL(GetDevFundPayment(120960, 12 * COIN), 12 * COIN * 6 / 100);
    BOOST_CHECK_EQUAL(GetDevFundPayment(120961, 12 * COIN), 12 * COIN * 5 / 100);
    BOOST_CHECK_EQUAL(GetDevFundPayment(1000000, 12 * COIN), 12 * COIN * 5 / 100);

    // launch: 3.00 dev fund, 6.30 smartnodes, 2.70 miners
    const CAmount dev = GetDevFundPayment(1, 12 * COIN);
    const CAmount mn = GetMasternodePayment(1, 12 * COIN - dev, Params().GetConsensus(), MnRewardEra::EvoReward);
    BOOST_CHECK_EQUAL(mn, 630000000);
    BOOST_CHECK_EQUAL(12 * COIN - dev - mn, 270000000);

    // the dev fund address is a valid multisig/script (M) address
    BOOST_CHECK(GetDevFundScript().IsPayToScriptHash());
}

BOOST_AUTO_TEST_CASE(btgs_collateral)
{
    BOOST_CHECK_EQUAL(GetMnType(MnType::Regular).collat_amount, 20000 * COIN);
    BOOST_CHECK_EQUAL(GetMnType(MnType::Evo).collat_amount, 80000 * COIN);
    BOOST_CHECK(dmn_types::IsCollateralAmount(20000 * COIN));
    BOOST_CHECK(!dmn_types::IsCollateralAmount(1000 * COIN));
}

BOOST_AUTO_TEST_SUITE_END()
