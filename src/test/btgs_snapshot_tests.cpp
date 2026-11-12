// Copyright (c) 2026 The BTGS Community developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <btgs/snapshot.h>
#include <chainparams.h>
#include <coins.h>
#include <consensus/merkle.h>
#include <primitives/block.h>
#include <script/script.h>
#include <script/standard.h>
#include <test/util/mining.h>
#include <test/util/setup_common.h>
#include <validation.h>

#include <boost/test/unit_test.hpp>

namespace {
//! Regtest with the built-in test list switched on (regtest has no list by default)
struct SnapshotTestingSetup : public TestingSetup {
    SnapshotTestingSetup() : TestingSetup{CBaseChainParams::REGTEST, {"-btgssnapshottest"}} {}
};

const CAmount TEST_TOTAL{125050000001};

CMutableTransaction CoinbaseWith(const std::vector<CTxOut>& outputs)
{
    CMutableTransaction tx;
    tx.vin.resize(1);
    tx.vout.emplace_back(500 * COIN, CScript() << OP_TRUE); // the miner's own output
    tx.vout.insert(tx.vout.end(), outputs.begin(), outputs.end());
    return tx;
}

std::shared_ptr<CBlock> WithCoinbase(std::shared_ptr<CBlock> block, const CMutableTransaction& coinbase)
{
    block->vtx[0] = MakeTransactionRef(coinbase);
    block->hashMerkleRoot = BlockMerkleRoot(*block);
    return block;
}
} // namespace

BOOST_AUTO_TEST_SUITE(btgs_snapshot_tests)

BOOST_FIXTURE_TEST_CASE(no_list_by_default, BasicTestingSetup)
{
    // mainnet (default for BasicTestingSetup): empty until the real snapshot is taken, fingerprint checked on load
    BOOST_CHECK(btgs::GetSnapshotOutputs().empty());
    BOOST_CHECK_EQUAL(btgs::GetSnapshotValue(btgs::SNAPSHOT_HEIGHT), 0);
    BOOST_CHECK_EQUAL(btgs::GetSnapshotHash({}).ToString(), "9a538906e6466ebd2617d321f71bc94e56056ce213d366773699e28158e00614");
    std::string err;
    BOOST_CHECK(btgs::CheckSnapshotCoinbase(CTransaction{CoinbaseWith({})}, btgs::SNAPSHOT_HEIGHT, err));
}

BOOST_FIXTURE_TEST_CASE(regtest_has_no_list_without_the_switch, RegTestingSetup)
{
    BOOST_CHECK(btgs::GetSnapshotOutputs().empty());
}

BOOST_FIXTURE_TEST_CASE(coinbase_check, SnapshotTestingSetup)
{
    const std::vector<CTxOut> list{btgs::GetSnapshotOutputs()};
    BOOST_REQUIRE_EQUAL(list.size(), 3U);
    BOOST_CHECK_EQUAL(btgs::GetSnapshotHash(list).ToString(), "6cc862c638f809fe8aa8030c84bef5d70140c679301d7f5e6a334e834584e9fa");
    BOOST_CHECK_EQUAL(btgs::GetSnapshotValue(btgs::SNAPSHOT_HEIGHT), TEST_TOTAL);
    BOOST_CHECK_EQUAL(btgs::GetSnapshotValue(0), 0);
    BOOST_CHECK_EQUAL(btgs::GetSnapshotValue(2), 0);
    for (const auto& out : list) BOOST_CHECK(out.scriptPubKey.IsPayToPublicKeyHash());

    std::string err;
    // exact list: accepted, in any order
    BOOST_CHECK(btgs::CheckSnapshotCoinbase(CTransaction{CoinbaseWith(list)}, 1, err));
    BOOST_CHECK(btgs::CheckSnapshotCoinbase(CTransaction{CoinbaseWith({list[2], list[0], list[1]})}, 1, err));
    // other heights have no rule
    BOOST_CHECK(btgs::CheckSnapshotCoinbase(CTransaction{CoinbaseWith({})}, 0, err));
    BOOST_CHECK(btgs::CheckSnapshotCoinbase(CTransaction{CoinbaseWith({})}, 2, err));

    // nothing paid
    BOOST_CHECK(!btgs::CheckSnapshotCoinbase(CTransaction{CoinbaseWith({})}, 1, err));
    BOOST_CHECK(!err.empty());
    // one output missing
    BOOST_CHECK(!btgs::CheckSnapshotCoinbase(CTransaction{CoinbaseWith({list[0], list[1]})}, 1, err));
    // one satoshi less, one satoshi more
    for (const CAmount delta : {-1, 1}) {
        auto changed{list};
        changed[1].nValue += delta;
        BOOST_CHECK(!btgs::CheckSnapshotCoinbase(CTransaction{CoinbaseWith(changed)}, 1, err));
    }
    // right amount, other key
    {
        auto changed{list};
        changed[2].scriptPubKey = GetScriptForDestination(PKHash(uint160{}));
        BOOST_CHECK(!btgs::CheckSnapshotCoinbase(CTransaction{CoinbaseWith(changed)}, 1, err));
    }
    // the same output twice does not replace a missing one
    BOOST_CHECK(!btgs::CheckSnapshotCoinbase(CTransaction{CoinbaseWith({list[0], list[1], list[1]})}, 1, err));

    // miner side
    CMutableTransaction tx{CoinbaseWith({})};
    btgs::AppendSnapshotOutputs(tx, 2);
    BOOST_CHECK_EQUAL(tx.vout.size(), 1U);
    btgs::AppendSnapshotOutputs(tx, 1);
    BOOST_CHECK_EQUAL(tx.vout.size(), 4U);
    BOOST_CHECK(btgs::CheckSnapshotCoinbase(CTransaction{tx}, 1, err));
}

BOOST_FIXTURE_TEST_CASE(block_1_pays_the_list, SnapshotTestingSetup)
{
    const std::vector<CTxOut> list{btgs::GetSnapshotOutputs()};
    const CScript miner_script{CScript() << OP_TRUE};
    auto height = [&] { return WITH_LOCK(::cs_main, return m_node.chainman->ActiveHeight()); };
    BOOST_REQUIRE_EQUAL(height(), 0);

    // the block template for block 1 already contains the list
    const CMutableTransaction good{*PrepareBlock(m_node, miner_script)->vtx[0]};
    std::string err;
    BOOST_REQUIRE(btgs::CheckSnapshotCoinbase(CTransaction{good}, 1, err));

    // block 1 without one of the outputs is rejected
    {
        CMutableTransaction cb{good};
        cb.vout.pop_back();
        auto block{WithCoinbase(PrepareBlock(m_node, miner_script), cb)};
        BOOST_CHECK(MineBlock(m_node, block).IsNull());
    }
    // block 1 with a changed amount is rejected
    {
        CMutableTransaction cb{good};
        cb.vout.back().nValue -= 1;
        auto block{WithCoinbase(PrepareBlock(m_node, miner_script), cb)};
        BOOST_CHECK(MineBlock(m_node, block).IsNull());
    }
    // block 1 that pays the list and then takes extra coins is rejected (value limit = reward + list total)
    {
        CMutableTransaction cb{good};
        cb.vout.emplace_back(1 * COIN, miner_script);
        auto block{WithCoinbase(PrepareBlock(m_node, miner_script), cb)};
        BOOST_CHECK(MineBlock(m_node, block).IsNull());
    }
    BOOST_CHECK_EQUAL(height(), 0);

    // the untouched block 1 is accepted and the coins exist
    auto block1{PrepareBlock(m_node, miner_script)};
    const uint256 cb_hash{block1->vtx[0]->GetHash()};
    BOOST_REQUIRE(!MineBlock(m_node, block1).IsNull());
    BOOST_CHECK_EQUAL(height(), 1);
    {
        LOCK(::cs_main);
        const CCoinsViewCache& coins{m_node.chainman->ActiveChainstate().CoinsTip()};
        CAmount found{0};
        for (uint32_t n = 0; n < block1->vtx[0]->vout.size(); ++n) {
            const Coin& coin{coins.AccessCoin(COutPoint{cb_hash, n})};
            for (const auto& out : list) {
                if (!coin.IsSpent() && coin.out == out) {
                    BOOST_CHECK(coin.IsCoinBase()); // normal coinbase maturity applies
                    found += coin.out.nValue;
                }
            }
        }
        BOOST_CHECK_EQUAL(found, TEST_TOTAL);
    }

    // block 2 has no snapshot outputs and no raised limit
    const CMutableTransaction cb2{*PrepareBlock(m_node, miner_script)->vtx[0]};
    for (const auto& out : cb2.vout) {
        for (const auto& snap : list) BOOST_CHECK(!(out == snap));
    }
    {
        CMutableTransaction cb{cb2};
        cb.vout.insert(cb.vout.end(), list.begin(), list.end());
        auto block{WithCoinbase(PrepareBlock(m_node, miner_script), cb)};
        BOOST_CHECK(MineBlock(m_node, block).IsNull());
    }
    BOOST_REQUIRE(!MineBlock(m_node, miner_script).IsNull());
    BOOST_CHECK_EQUAL(height(), 2);
}

struct TestnetSnapshotSetup : public BasicTestingSetup {
    TestnetSnapshotSetup() : BasicTestingSetup{CBaseChainParams::TESTNET} {}
};

BOOST_FIXTURE_TEST_CASE(testnet_list_pays_exact_collateral, TestnetSnapshotSetup)
{
    // The testnet list funds the smartnode tests: 30 outputs of exactly 20,000 (one collateral each) + 5 x 1,000
    const std::vector<CTxOut>& list = btgs::GetSnapshotOutputs(); // also checks the pinned fingerprint
    BOOST_CHECK_EQUAL(list.size(), 35U);
    CAmount total{0};
    size_t collateral{0}, small{0};
    for (const CTxOut& out : list) {
        total += out.nValue;
        if (out.nValue == 20000 * COIN) ++collateral;
        if (out.nValue == 1000 * COIN) ++small;
        BOOST_CHECK_EQUAL(out.scriptPubKey.size(), 25U);
        BOOST_CHECK(out.scriptPubKey[0] == OP_DUP && out.scriptPubKey[1] == OP_HASH160);
    }
    BOOST_CHECK_EQUAL(collateral, 30U);
    BOOST_CHECK_EQUAL(small, 5U);
    BOOST_CHECK_EQUAL(total, 605000 * COIN);
    BOOST_CHECK_EQUAL(btgs::GetSnapshotValue(1), total);
    BOOST_CHECK_EQUAL(btgs::GetSnapshotValue(2), 0);
}

BOOST_AUTO_TEST_SUITE_END()
