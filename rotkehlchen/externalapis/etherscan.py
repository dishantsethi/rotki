import logging
from json.decoder import JSONDecodeError
from typing import Any, Dict, List, Optional, Union, overload

import requests
from eth_utils.address import to_checksum_address
from typing_extensions import Literal

from rotkehlchen.assets.asset import EthereumToken
from rotkehlchen.db.dbhandler import DBHandler
from rotkehlchen.errors import DeserializationError, RemoteError
from rotkehlchen.fval import FVal
from rotkehlchen.serialization.deserialize import deserialize_fval, deserialize_timestamp
from rotkehlchen.typing import ChecksumEthAddress, EthereumTransaction
from rotkehlchen.user_messages import MessagesAggregator
from rotkehlchen.utils.misc import convert_to_int, from_wei, hexstring_to_bytes
from rotkehlchen.utils.serialization import rlk_jsonloads_dict

logger = logging.getLogger(__name__)


def read_hash(data: Dict[str, Any], key: str) -> bytes:
    try:
        result = hexstring_to_bytes(data[key])
    except ValueError:
        raise DeserializationError(
            f'Failed to read {key} as a hash during etherscan transaction query',
        )
    return result


def read_integer(data: Dict[str, Any], key: str) -> int:
    try:
        result = convert_to_int(data[key])
    except ValueError:
        raise DeserializationError(
            f'Failed to read {key} as an integer during etherscan transaction query',
        )
    return result


def deserialize_transaction_from_etherscan(
        data: Dict[str, Any],
        internal: bool,
) -> EthereumTransaction:
    """Reads dict data of a transaction from etherscan and deserializes it

    Can raise DeserializationError if something is wrong
    """
    try:
        # internal tx list contains no gasprice
        gas_price = FVal(-1) if internal else FVal(data['gasPrice'])
        tx_hash = read_hash(data, 'hash')
        input_data = read_hash(data, 'input')
        timestamp = deserialize_timestamp(data['timeStamp'])

        block_number = read_integer(data, 'blockNumber')
        nonce = -1 if internal else read_integer(data, 'nonce')

        return EthereumTransaction(
            timestamp=timestamp,
            block_number=block_number,
            tx_hash=tx_hash,
            from_address=data['from'],
            to_address=data['to'],
            value=deserialize_fval(data['value']),
            gas=deserialize_fval(data['gas']),
            gas_price=gas_price,
            gas_used=deserialize_fval(data['gasUsed']),
            input_data=input_data,
            nonce=nonce,
        )
    except KeyError as e:
        raise DeserializationError(f'Etherscan ethereum transaction missing expected key {str(e)}')


class Etherscan():
    def __init__(self, database: DBHandler, msg_aggregator: MessagesAggregator) -> None:
        self.db = database
        self.msg_aggregator = msg_aggregator
        self.session = requests.session()
        self.session.headers.update({'User-Agent': 'rotkehlchen'})

    @overload  # noqa: F811
    def _query(  # pylint: disable=no-self-use
            self,
            module: str,
            action: Literal['balancemulti', 'txlist', 'txlistinternal'],
            options: Optional[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        ...

    @overload  # noqa: F811
    def _query(  # noqa: F811 pylint: disable=no-self-use
            self,
            module: str,
            action: Literal['balance', 'tokenbalance'],
            options: Optional[Dict[str, str]],
    ) -> str:
        ...

    def _query(  # noqa: F811
            self,
            module: str,
            action: str,
            options: Optional[Dict[str, str]],
    ) -> Union[List[Dict[str, Any]], str, List[EthereumTransaction]]:
        """Queries etherscan

        May raise:
        - RemoteError if there are any problems with reaching Etherscan or if
        an unexpected response is returned
        """
        query_str = f'https://api.etherscan.io/api?module={module}&action={action}'
        if options:
            for name, value in options.items():
                query_str += f'&{name}={value}'

        logger.debug(f'Querying etherscan: {query_str}')

        try:
            response = self.session.get(query_str)
        except requests.exceptions.ConnectionError as e:
            raise RemoteError(f'Etherscan API request failed due to {str(e)}')

        if response.status_code != 200:
            raise RemoteError(
                f'Etherscan API request {response.url} failed '
                f'with HTTP status code {response.status_code} and text '
                f'{response.text}',
            )

        try:
            json_ret = rlk_jsonloads_dict(response.text)
        except JSONDecodeError:
            raise RemoteError(f'Etherscan returned invalid JSON response: {response.text}')

        try:
            result = json_ret['result']
            status = json_ret['status']
            if status != 1:
                transaction_endpoint_and_none_found = (
                    status == 0 and
                    json_ret['message'] == 'No transactions found' and
                    'txlist' in action
                )
                if transaction_endpoint_and_none_found:
                    # Can't realize that result is always a list here so we ignnore mypy warning
                    return []  # type: ignore
                # else
                raise RemoteError(f'Etherscan returned error response: {json_ret}')
        except KeyError as e:
            raise RemoteError(
                f'Unexpected format of Etherscan response. Missing key entry for {str(e)}',
            )

        return result

    def get_account_balance(self, account: ChecksumEthAddress) -> FVal:
        """Gets the balance of the given account in WEI

        May raise:
        - RemoteError due to self._query(). Also if the returned result can't be parsed as a number
        """
        result = self._query(module='account', action='balance', options={'address': account})
        try:
            amount = FVal(result)
        except ValueError:
            raise RemoteError(
                f'Etherscan returned non-numeric result for account balance {result}',
            )
        return amount

    def get_accounts_balance(
            self,
            accounts: List[ChecksumEthAddress],
    ) -> Dict[ChecksumEthAddress, FVal]:
        """Gets the balance of the given accounts in ETH

        May raise:
        - RemoteError due to self._query(). Also if the returned result
        is not in the expected format
        """
        # Etherscan can only accept up to 20 accounts in the multi account balance endpoint
        if len(accounts) > 20:
            new_accounts = [accounts[x:x + 2] for x in range(0, len(accounts), 2)]
        else:
            new_accounts = [accounts]

        balances = {}
        for account_slice in new_accounts:
            result = self._query(
                module='account',
                action='balancemulti',
                options={'address': ','.join(account_slice)},
            )
            if not isinstance(result, list):
                raise RemoteError(
                    f'Etherscan multibalance result {result} is in unexpected format',
                )

            try:
                for account_entry in result:
                    amount = FVal(account_entry['balance'])
                    # Etherscan does not return accounts checksummed so make sure they
                    # are converted properly here
                    checksum_account = to_checksum_address(account_entry['account'])
                    balances[checksum_account] = from_wei(amount)
                    logger.debug(
                        'Etherscan account balance result',
                        sensitive_log=True,
                        eth_address=account_entry['account'],
                        wei_amount=amount,
                    )
            except (KeyError, ValueError):
                raise RemoteError(
                    'Unexpected data format in etherscan multibalance response: {result}',
                )

        return balances

    def get_token_balance(
            self,
            token: EthereumToken,
            account: ChecksumEthAddress,
    ) -> FVal:
        """Gets the token balance of the given account.
        The returned balance is adjusted for token decimals.

        May raise:
        - RemoteError due to self._query(). Also if the returned result
        is not in the expected format
        """
        result = self._query(
            module='account',
            action='tokenbalance',
            options={'contractaddress': token.ethereum_address, 'address': account},
        )

        try:
            token_amount = FVal(result)
        except ValueError:
            raise RemoteError(
                f'Etherscan returned non-numeric result for account token balance {result}',
            )

        return token_amount / (FVal(10) ** FVal(token.decimals))

    def get_transactions(
            self,
            account: ChecksumEthAddress,
            internal: bool,
            from_block: Optional[int] = None,
            to_block: Optional[int] = None,
    ) -> List[EthereumTransaction]:
        """Gets a list of transactions (either normal or internal) for account.

        May raise:
        - RemoteError due to self._query(). Also if the returned result
        is not in the expected format
        """
        options = {'address': str(account)}
        if from_block:
            options['startBlock'] = str(from_block)
        if to_block:
            options['endBlock'] = str(to_block)
        action: Literal['txlistinternal', 'txlist'] = 'txlistinternal' if internal else 'txlist'

        result = self._query(module='account', action=action, options=options)
        transactions = []
        for entry in result:
            try:
                tx = deserialize_transaction_from_etherscan(data=entry, internal=internal)
            except DeserializationError as e:
                self.msg_aggregator.add_warning(f'{str(e)}. Skipping transaction')
                continue

            transactions.append(tx)

        return transactions
