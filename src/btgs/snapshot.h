// Copyright (c) 2026 The BTGS Community developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef BTGS_SNAPSHOT_H
#define BTGS_SNAPSHOT_H

#include <consensus/amount.h>
#include <primitives/transaction.h>
#include <uint256.h>

#include <string>
#include <vector>

/**
 * Balances carried over from the old BTGS chain.
 *
 * The list (one output per key, see btgs/snapshot_data.h) is built into the node and paid out by the
 * coinbase of block SNAPSHOT_HEIGHT. That block is only valid if its coinbase contains every output of
 * the list; its value limit is raised by exactly the list total. The outputs follow the normal coinbase
 * maturity rule.
 */
namespace btgs {

/** The block that pays out the carried-over balances (genesis outputs cannot be spent, so not block 0). */
static constexpr int SNAPSHOT_HEIGHT{1};

/** Carried-over outputs of the active network (empty if the network has none). */
const std::vector<CTxOut>& GetSnapshotOutputs();

/** Extra coinbase value allowed at this height: the list total at SNAPSHOT_HEIGHT, otherwise 0. */
CAmount GetSnapshotValue(int nHeight);

/** Fingerprint of a list: double SHA-256 of the serialized outputs. */
uint256 GetSnapshotHash(const std::vector<CTxOut>& outputs);

/** At SNAPSHOT_HEIGHT the coinbase must contain every output of the list (each coinbase output counts once). */
bool CheckSnapshotCoinbase(const CTransaction& coinbase, int nHeight, std::string& strErrorRet);

/** Miner side: add the list to the coinbase at SNAPSHOT_HEIGHT. */
void AppendSnapshotOutputs(CMutableTransaction& coinbase, int nHeight);

} // namespace btgs

#endif // BTGS_SNAPSHOT_H
