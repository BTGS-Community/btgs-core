// Copyright (c) 2026 The BTGS Community developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <btgs/snapshot.h>

#include <btgs/snapshot_data.h>
#include <chainparams.h>
#include <chainparamsbase.h>
#include <hash.h>
#include <script/script.h>
#include <script/standard.h>
#include <tinyformat.h>
#include <util/strencodings.h>
#include <util/system.h>

#include <cassert>
#include <map>
#include <mutex>
#include <utility>

namespace btgs {
namespace {

// Fingerprints of the built-in lists (printed by contrib/snapshot/generate-snapshot.py).
// The node refuses to start if a list does not match: a changed list must show up here as well.
const uint256 EXPECTED_MAIN{uint256S("0x9a538906e6466ebd2617d321f71bc94e56056ce213d366773699e28158e00614")}; // empty until the snapshot is taken
const uint256 EXPECTED_TEST{uint256S("0xac2bb8d51b460853c1fd163f819f7b8692e4ba4dc5f58470305de47e0506a633")}; // testnet list: 35 outputs, 605000 test BTGS (contrib/snapshot/make-testnet-keys.py)

std::vector<CTxOut> BuildOutputs(const std::vector<std::pair<const char*, int64_t>>& raw)
{
    std::vector<CTxOut> outputs;
    outputs.reserve(raw.size());
    CAmount total{0};
    for (const auto& [key_hex, amount] : raw) {
        const std::vector<unsigned char> key{ParseHex(key_hex)};
        assert(key.size() == 20);
        assert(amount > 0 && MoneyRange(amount));
        total += amount;
        assert(MoneyRange(total));
        outputs.emplace_back(amount, GetScriptForDestination(PKHash(uint160(key))));
    }
    return outputs;
}

} // namespace

uint256 GetSnapshotHash(const std::vector<CTxOut>& outputs)
{
    CHashWriter ss(SER_GETHASH, 0);
    ss << outputs;
    return ss.GetHash();
}

const std::vector<CTxOut>& GetSnapshotOutputs()
{
    static std::mutex mutex;
    static std::map<std::string, std::vector<CTxOut>> cache;

    const std::string chain{Params().NetworkIDString()};
    // Regtest has no list by default, so the test chains stay as they are; tests switch the test list on
    const bool test_list{chain == CBaseChainParams::REGTEST && gArgs.GetBoolArg("-btgssnapshottest", false)};
    const std::string id{test_list ? chain + "+testlist" : chain};

    std::lock_guard<std::mutex> lock(mutex);
    auto it = cache.find(id);
    if (it == cache.end()) {
        std::vector<CTxOut> outputs;
        if (chain == CBaseChainParams::MAIN) {
            outputs = BuildOutputs(SNAPSHOT_MAIN);
            assert(GetSnapshotHash(outputs) == EXPECTED_MAIN);
        } else if (chain == CBaseChainParams::TESTNET) {
            outputs = BuildOutputs(SNAPSHOT_TEST);
            assert(GetSnapshotHash(outputs) == EXPECTED_TEST);
        } else if (test_list) {
            outputs = BuildOutputs(SNAPSHOT_REGTEST_TEST);
        }
        it = cache.emplace(id, std::move(outputs)).first;
    }
    return it->second;
}

CAmount GetSnapshotValue(int nHeight)
{
    if (nHeight != SNAPSHOT_HEIGHT) return 0;
    CAmount total{0};
    for (const auto& out : GetSnapshotOutputs()) total += out.nValue;
    return total;
}

bool CheckSnapshotCoinbase(const CTransaction& coinbase, int nHeight, std::string& strErrorRet)
{
    strErrorRet.clear();
    if (nHeight != SNAPSHOT_HEIGHT) return true;

    // count the coinbase outputs, then take one for every output of the list
    std::map<std::pair<CScript, CAmount>, int> available;
    for (const auto& out : coinbase.vout) ++available[{out.scriptPubKey, out.nValue}];

    for (const auto& out : GetSnapshotOutputs()) {
        auto it = available.find({out.scriptPubKey, out.nValue});
        if (it == available.end() || it->second == 0) {
            strErrorRet = strprintf("block %d does not pay the snapshot output %s (%d satoshis)",
                                    nHeight, HexStr(out.scriptPubKey), out.nValue);
            return false;
        }
        --it->second;
    }
    return true;
}

void AppendSnapshotOutputs(CMutableTransaction& coinbase, int nHeight)
{
    if (nHeight != SNAPSHOT_HEIGHT) return;
    const auto& outputs{GetSnapshotOutputs()};
    coinbase.vout.insert(coinbase.vout.end(), outputs.begin(), outputs.end());
}

} // namespace btgs
