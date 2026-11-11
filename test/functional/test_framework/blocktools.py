#!/usr/bin/env python3
# Copyright (c) 2015-2022 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Utilities for manipulating blocks and transactions."""

from decimal import Decimal
import struct
import time
import unittest

from .messages import (
    CBlock,
    CCbTx,
    COIN,
    COutPoint,
    CTransaction,
    CTxIn,
    CTxOut,
    SEQUENCE_FINAL,
    tx_from_hex,
    from_hex,
    uint256_to_string,
)
from .script import (
    CScript,
    CScriptNum,
    CScriptOp,
    OP_TRUE
)
from .script_util import (
    key_to_p2pk_script,
    keyhash_to_p2pkh_script,
)
from .util import assert_equal

MAX_BLOCK_SIGOPS = 40000

# BTGS: regtest reward rules (see GetBlockSubsidyHelper / GetDevFundPayment in C++)
BTGS_REGTEST_SUBSIDY_INTERVAL = 150
# regtest dev fund address tVkDMN8j3kdq5JHAa2twBjBoXt7KFXfL3x
BTGS_REGTEST_DEVFUND_SCRIPT = keyhash_to_p2pkh_script(bytes.fromhex("fa53c9728c3189b12b267be5811b54033525b08d"))
BTGS_REGTEST_DEVFUND_ADDRESS = "tVkDMN8j3kdq5JHAa2twBjBoXt7KFXfL3x"

def get_block_subsidy(height):
    """BTGS regtest block reward in satoshis: 625 (20% dev fund -> 500 miner, Dash's test amount; mainnet is 12), cut by 1/14 every 150 blocks"""
    subsidy = 625 * COIN
    i = BTGS_REGTEST_SUBSIDY_INTERVAL
    while i <= height - 1:
        subsidy -= subsidy // 14
        i += BTGS_REGTEST_SUBSIDY_INTERVAL
    return subsidy

def get_dev_fund_payment(height, subsidy=None):
    """BTGS dev fund in satoshis: 25% at launch, -1 point every 6,048 blocks, 5% floor"""
    if height < 1:
        return 0
    if subsidy is None:
        subsidy = get_block_subsidy(height)
    pct = max(5, 20 - (height - 1) // 6048)  # regtest starts at 20% (mainnet/testnet 25%)
    return subsidy * pct // 100

# Genesis block time (regtest)
TIME_GENESIS_BLOCK = 1417713337

MAX_FUTURE_BLOCK_TIME = 2 * 60 * 60

# Coinbase transaction outputs can only be spent after this number of new blocks (network rule)
COINBASE_MATURITY = 100

NORMAL_GBT_REQUEST_PARAMS = {"rules": []} # type: ignore[var-annotated]

VERSIONBITS_LAST_OLD_BLOCK_VERSION = 4
MIN_BLOCKS_TO_KEEP = 288

def create_block(hashprev=None, coinbase=None, ntime=None, *, version=None, tmpl=None, txlist=None, dip4_activated=False, v20_activated=False):
    """Create a block (with regtest difficulty)."""
    block = CBlock()
    if tmpl is None:
        tmpl = {}
    block.nVersion = version or tmpl.get('version') or VERSIONBITS_LAST_OLD_BLOCK_VERSION
    block.nTime = ntime or tmpl.get('curtime') or int(time.time() + 600)
    block.hashPrevBlock = hashprev or int(tmpl['previousblockhash'], 0x10)
    if tmpl and not tmpl.get('bits') is None:
        block.nBits = struct.unpack('>I', bytes.fromhex(tmpl['bits']))[0]
    else:
        block.nBits = 0x207fffff  # difficulty retargeting is disabled in REGTEST chainparams
    if coinbase is None:
        coinbase = create_coinbase(height=tmpl['height'], dip4_activated=dip4_activated, v20_activated=v20_activated)
    block.vtx.append(coinbase)
    if txlist:
        for tx in txlist:
            if not hasattr(tx, 'calc_sha256'):
                tx = tx_from_hex(tx)
            block.vtx.append(tx)
    block.hashMerkleRoot = block.calc_merkle_root()
    block.calc_sha256()
    return block

# TODO: implement MN_RR support here or remove it
def create_block_with_mnpayments(mninfo, node, vtx=None, mn_payee=None, mn_amount=None):
    if vtx is None:
        vtx = []
    bt = node.getblocktemplate()
    height = bt['height']
    tip_hash = bt['previousblockhash']
    coinbasevalue = bt['coinbasevalue']

    assert len(bt['masternode']) <= 2
    if mn_payee is None:
        mn_payee = bt['masternode'][0]['payee']

    mn_operator_payee = None
    if len(bt['masternode']) == 2:
        mn_operator_payee = bt['masternode'][1]['payee']
    # we can't take the masternode payee amount from the template here as we might have additional fees in vtx

    # calculate fees that the block template included (we'll have to remove it from the coinbase as we won't
    # include the template's transactions
    bt_fees = 0
    for tx in bt['transactions']:
        bt_fees += tx['fee']

    new_fees = 0
    for tx in vtx:
        in_value = 0
        out_value = 0
        for txin in tx.vin:
            txout = node.gettxout(uint256_to_string(txin.prevout.hash), txin.prevout.n, False)
            in_value += int(txout['value'] * COIN)
        for txout in tx.vout:
            out_value += txout.nValue
        new_fees += in_value - out_value

    # fix fees
    coinbasevalue -= bt_fees
    coinbasevalue += new_fees

    operator_reward = 0
    if mn_operator_payee is not None:
        for mn in mninfo:
            if mn.rewards_address == mn_payee:
                operator_reward = mn.operator_reward
                break
        assert operator_reward > 0

    mn_operator_amount = 0
    if mn_amount is None:
        v20_info = node.getdeploymentinfo()['deployments']['v20']
        mn_amount_total = get_masternode_payment(height, coinbasevalue, v20_info['active'])
        mn_operator_amount = mn_amount_total * operator_reward // 100
        mn_amount = mn_amount_total - mn_operator_amount
    miner_amount = coinbasevalue - mn_amount - mn_operator_amount

    dev_fund = get_dev_fund_payment(height)
    miner_amount -= dev_fund
    miner_address = node.get_deterministic_priv_key().address
    outputs = {miner_address: str(Decimal(miner_amount) / COIN)}
    if dev_fund > 0:
        outputs[BTGS_REGTEST_DEVFUND_ADDRESS] = str(Decimal(dev_fund) / COIN)
    if mn_amount > 0:
        outputs[mn_payee] = str(Decimal(mn_amount) / COIN)
    if mn_operator_amount > 0:
        outputs[mn_operator_payee] = str(Decimal(mn_operator_amount) / COIN)

    coinbase = tx_from_hex(node.createrawtransaction([], outputs))
    coinbase.vin = create_coinbase(height).vin

    # We can't really use this one as it would result in invalid merkle roots for masternode lists
    if len(bt['coinbase_payload']) != 0:
        tip_block = node.getblock(tip_hash)
        cbtx = from_hex(CCbTx(version=1), bt['coinbase_payload'])
        if 'cbTx' in tip_block:
            cbtx.merkleRootMNList = int(tip_block['cbTx']['merkleRootMNList'], 16)
        else:
            cbtx.merkleRootMNList = 0
        coinbase.nVersion = 3
        coinbase.nType = 5 # CbTx
        coinbase.vExtraPayload = cbtx.serialize()

    coinbase.calc_sha256()

    block = create_block(int(tip_hash, 16), coinbase, ntime=bt['curtime'], version=bt['version'])
    block.vtx += vtx

    # Add quorum commitments from template
    for tx in bt['transactions']:
        tx2 = tx_from_hex(tx['data'])
        if tx2.nType == 6:
            block.vtx.append(tx2)

    block.hashMerkleRoot = block.calc_merkle_root()
    block.solve()
    return block

def script_BIP34_coinbase_height(height):
    if height <= 16:
        res = CScriptOp.encode_op_n(height)
        # Append dummy to increase scriptSig size above 2 (see bad-cb-length consensus rule)
        return CScript([res, OP_TRUE])
    return CScript([CScriptNum(height)])


def create_coinbase(height, pubkey=None, *, script_pubkey=None, dip4_activated=False, v20_activated=False, nValue=None):
    """Create a coinbase transaction, assuming no miner fees.

    If pubkey is passed in, the coinbase output will be a P2PK output;
    otherwise an anyone-can-spend output."""
    coinbase = CTransaction()
    coinbase.vin.append(CTxIn(COutPoint(0, 0xffffffff), script_BIP34_coinbase_height(height), SEQUENCE_FINAL))
    coinbaseoutput = CTxOut()
    dev_fund = get_dev_fund_payment(height)
    if nValue is None:
        coinbaseoutput.nValue = get_block_subsidy(height) - dev_fund  # BTGS: reward minus dev fund
    else:
        coinbaseoutput.nValue = int(nValue * COIN)
    if (pubkey is not None):
        coinbaseoutput.scriptPubKey = key_to_p2pk_script(pubkey)
    elif script_pubkey is not None:
        coinbaseoutput.scriptPubKey = script_pubkey
    else:
        coinbaseoutput.scriptPubKey = CScript([OP_TRUE])
    coinbase.vout = [coinbaseoutput]
    if dev_fund > 0:
        coinbase.vout.append(CTxOut(dev_fund, BTGS_REGTEST_DEVFUND_SCRIPT))  # BTGS: dev fund
    if dip4_activated:
        coinbase.nVersion = 3
        coinbase.nType = 5
        cbtx_version = 3 if v20_activated else 2
        cbtx_payload = CCbTx(cbtx_version, height, 0, 0, 0)
        coinbase.vExtraPayload = cbtx_payload.serialize()
    coinbase.calc_sha256()
    return coinbase

def create_tx_with_script(prevtx, n, script_sig=b"", *, amount, script_pub_key=CScript()):
    """Return one-input, one-output transaction object
       spending the prevtx's n-th output with the given amount.

       Can optionally pass scriptPubKey and scriptSig, default is anyone-can-spend output.
    """
    tx = CTransaction()
    assert n < len(prevtx.vout)
    tx.vin.append(CTxIn(COutPoint(prevtx.sha256, n), script_sig, SEQUENCE_FINAL))
    tx.vout.append(CTxOut(amount, script_pub_key))
    tx.calc_sha256()
    return tx

def get_legacy_sigopcount_block(block, accurate=True):
    count = 0
    for tx in block.vtx:
        count += get_legacy_sigopcount_tx(tx, accurate)
    return count

def get_legacy_sigopcount_tx(tx, accurate=True):
    count = 0
    for i in tx.vout:
        count += i.scriptPubKey.GetSigOpCount(accurate)
    for j in tx.vin:
        # scriptSig might be of type bytes, so convert to CScript for the moment
        count += CScript(j.scriptSig).GetSigOpCount(accurate)
    return count

"""
Dash chaintips rpc returns extra info in each tip (difficulty, chainwork, and
forkpoint). Filter down to relevant ones checked in this test.
"""
def filter_tip_keys(chaintips):
    check_keys = ["hash", "height", "branchlen", "status"]
    filtered_tips = []
    for tip in chaintips:
        filtered_tips.append({k: tip[k] for k in check_keys})
    return filtered_tips

# Identical to GetMasternodePayment in C++ code (BTGS)
def get_masternode_payment(nHeight, blockValue, fV20Active):
    """blockValue = block reward + fees; smartnodes get 70% of what is left after the dev fund"""
    return (blockValue - get_dev_fund_payment(nHeight)) * 7 // 10

class TestFrameworkBlockTools(unittest.TestCase):
    def test_create_coinbase(self):
        height = 20
        coinbase_tx = create_coinbase(height=height)
        assert_equal(CScriptNum.decode(coinbase_tx.vin[0].scriptSig), height)
