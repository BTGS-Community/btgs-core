// Copyright (c) 2023-2024 The Dash Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef BITCOIN_EVO_DMN_TYPES_H
#define BITCOIN_EVO_DMN_TYPES_H

#include <consensus/amount.h>

#include <limits>
#include <string_view>

enum class MnType : uint16_t {
    Regular = 0,
    Evo = 1,
    COUNT,
    Invalid = std::numeric_limits<uint16_t>::max(),
};

template<typename T> struct is_serializable_enum;
template<> struct is_serializable_enum<MnType> : std::true_type {};

namespace dmn_types {

struct mntype_struct
{
    const int32_t voting_weight{0};
    const CAmount collat_amount{0};
    const std::string_view description;
};

constexpr auto Regular = mntype_struct{
    .voting_weight = 1,
    .collat_amount = 1000 * COIN, // regtest/devnet (Dash test amount); mainnet/testnet: see GetMnType
    .description = "Regular",
};
constexpr auto Evo = mntype_struct{
    .voting_weight = 4,
    .collat_amount = 4000 * COIN, // regtest/devnet (Dash test amount); mainnet/testnet: see GetMnType
    .description = "Evo",
};
constexpr auto Invalid = mntype_struct{
    .voting_weight = 0,
    .collat_amount = MAX_MONEY,
    .description = "Invalid",
};

// BTGS: real collateral on mainnet and testnet
constexpr auto BtgsRegular = mntype_struct{
    .voting_weight = 1,
    .collat_amount = 20000 * COIN, // BTGS: smartnode collateral
    .description = "Regular",
};
constexpr auto BtgsEvo = mntype_struct{
    .voting_weight = 4,
    .collat_amount = 80000 * COIN, // BTGS: EvoNode (not used, Dash Platform only; decide later)
    .description = "Evo",
};

} // namespace dmn_types

/** BTGS: collateral depends on the network (mainnet/testnet: BTGS amounts, regtest/devnet: Dash test amounts). Defined in chainparams.cpp */
[[nodiscard]] dmn_types::mntype_struct GetMnType(MnType type);

namespace dmn_types {
[[nodiscard]] inline bool IsCollateralAmount(CAmount amount)
{
    return amount == GetMnType(MnType::Regular).collat_amount ||
        amount == GetMnType(MnType::Evo).collat_amount;
}
} // namespace dmn_types

[[nodiscard]] constexpr bool IsValidMnType(MnType type) { return type < MnType::COUNT; }

#endif // BITCOIN_EVO_DMN_TYPES_H
