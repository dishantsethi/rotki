from typing import Final

from rotkehlchen.types import SUPPORTED_BLOCKCHAIN_TO_CHAINID, SupportedBlockchain

DEFAULT_EVM_RPC_TIMEOUT = 10
NON_BITCOIN_CHAINS = [
    SupportedBlockchain.AVALANCHE,
    SupportedBlockchain.POLKADOT,
    SupportedBlockchain.ETHEREUM_BEACONCHAIN,
    SupportedBlockchain.KUSAMA,
] + list(SUPPORTED_BLOCKCHAIN_TO_CHAINID.keys())

LAST_EVM_ACCOUNTS_DETECT_KEY: Final = 'last_evm_accounts_detect_ts'
