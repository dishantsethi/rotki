import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Optional, TypeVar

from rotkehlchen.accounting.ledger_actions import LedgerActionType
from rotkehlchen.accounting.mixins.event import AccountingEventMixin, AccountingEventType
from rotkehlchen.accounting.structures.base import HistoryBaseEntry
from rotkehlchen.accounting.structures.evm_event import EvmEvent
from rotkehlchen.accounting.structures.types import HistoryEventSubType, HistoryEventType
from rotkehlchen.chain.evm.accounting.structures import (
    BaseEventSettings,
    TxAccountingTreatment,
    TxEventSettings,
)
from rotkehlchen.chain.evm.decoding.constants import CPT_GAS
from rotkehlchen.constants.misc import ONE
from rotkehlchen.logging import RotkehlchenLogsAdapter
from rotkehlchen.types import Price, Timestamp

if TYPE_CHECKING:
    from rotkehlchen.accounting.pot import AccountingPot
    from rotkehlchen.chain.evm.accounting.aggregator import EVMAccountingAggregators

logger = logging.getLogger(__name__)
log = RotkehlchenLogsAdapter(logger)


def make_default_accounting_settings(pot: 'AccountingPot') -> dict[str, BaseEventSettings]:
    """
    Returns accounting settings for events that can come from various decoders and thus don't have
    any particular protocol. These settings also allow users to customize events in the UI.
    Users are supposed to apply these settings in the history view once they become customizable:
    https://github.com/rotki/rotki/issues/4341
    """
    result = {}
    gas_key = str(HistoryEventType.SPEND) + '__' + str(HistoryEventSubType.FEE) + '__' + CPT_GAS  # noqa: E501
    result[gas_key] = BaseEventSettings(
        taxable=pot.settings.include_gas_costs,
        count_entire_amount_spend=pot.settings.include_gas_costs,
        count_cost_basis_pnl=pot.settings.include_crypto2crypto,
        method='spend',
    )
    spend_key = str(HistoryEventType.SPEND) + '__' + str(HistoryEventSubType.NONE)
    result[spend_key] = BaseEventSettings(
        taxable=True,
        count_entire_amount_spend=True,
        count_cost_basis_pnl=True,
        method='spend',
    )
    receive_key = str(HistoryEventType.RECEIVE) + '__' + str(HistoryEventSubType.NONE)
    result[receive_key] = BaseEventSettings(
        taxable=True,
        count_entire_amount_spend=True,
        count_cost_basis_pnl=True,
        method='acquisition',
    )
    deposit_key = str(HistoryEventType.DEPOSIT) + '__' + str(HistoryEventSubType.NONE)
    result[deposit_key] = BaseEventSettings(
        taxable=False,
        count_entire_amount_spend=False,
        count_cost_basis_pnl=False,
        method='spend',
    )
    withdraw_key = str(HistoryEventType.WITHDRAWAL) + '__' + str(HistoryEventSubType.NONE)
    result[withdraw_key] = BaseEventSettings(
        taxable=False,
        count_entire_amount_spend=False,
        count_cost_basis_pnl=False,
        method='acquisition',
    )
    fee_key = str(HistoryEventType.SPEND) + '__' + str(HistoryEventSubType.FEE)
    result[fee_key] = BaseEventSettings(
        taxable=True,
        count_entire_amount_spend=True,
        count_cost_basis_pnl=True,
        method='spend',
    )
    renew_key = str(HistoryEventType.RENEW) + '__' + str(HistoryEventSubType.NONE)
    result[renew_key] = BaseEventSettings(
        taxable=True,
        count_entire_amount_spend=True,
        count_cost_basis_pnl=True,
        method='spend',
    )
    swap_key = str(HistoryEventType.TRADE) + '__' + str(HistoryEventSubType.SPEND)
    result[swap_key] = BaseEventSettings(
        taxable=True,
        count_entire_amount_spend=False,
        count_cost_basis_pnl=True,
        method='spend',
        accounting_treatment=TxAccountingTreatment.SWAP,
    )
    airdrop_key = str(HistoryEventType.RECEIVE) + '__' + str(HistoryEventSubType.AIRDROP)
    result[airdrop_key] = BaseEventSettings(
        taxable=LedgerActionType.AIRDROP in pot.settings.taxable_ledger_actions,
        # count_entire_amount_spend and count_cost_basis_pnl don't matter for acquisitions.
        count_entire_amount_spend=False,
        count_cost_basis_pnl=False,
        method='acquisition',
    )
    reward_key = str(HistoryEventType.RECEIVE) + '__' + str(HistoryEventSubType.REWARD)
    result[reward_key] = BaseEventSettings(
        taxable=True,
        # count_entire_amount_spend and count_cost_basis_pnl don't matter for acquisitions.
        count_entire_amount_spend=False,
        count_cost_basis_pnl=False,
        method='acquisition',
    )
    return result


T = TypeVar('T', bound=HistoryBaseEntry)


def history_base_entries_iterator(
        events_iterator: Iterator[AccountingEventMixin],
        associated_event: T,
) -> Iterator[T]:
    """
    Takes an iterator of accounting events and transforms it into a history base entries iterator.
    Takes associated event as an argument to be able to log it in case of errors.
    """
    for event in events_iterator:
        if isinstance(event, type(associated_event)) is False:
            log.error(
                f'At accounting for event {associated_event.notes} with identifier '
                f'{associated_event.event_identifier} we expected to take an additional '
                f'event but found a non {type(associated_event)} event',
            )
            return

        yield event  # type: ignore[misc]  # event is guaranteed to be of type T


class EventsAccountant:
    """
    This class contains the different rules applied to history events during the accounting
    process. It applies special rules for evm events and also the default defined rules.
    """

    def __init__(
            self,
            evm_accounting_aggregators: 'EVMAccountingAggregators',
            pot: 'AccountingPot',
    ) -> None:
        self.evm_accounting_aggregators = evm_accounting_aggregators
        self.pot = pot
        self.event_settings: dict[str, BaseEventSettings] = {}

    def reset(self) -> None:
        self.evm_accounting_aggregators.reset()
        self.event_settings = (  # Using | operator is fine since keys are unique
            self.evm_accounting_aggregators.get_accounting_settings(self.pot) |
            make_default_accounting_settings(self.pot)
        )

    def process(
            self,
            event: HistoryBaseEntry,
            events_iterator: Iterator[AccountingEventMixin],
    ) -> int:
        """Process a history base entry and return number of actions consumed from the iterator"""
        timestamp = event.get_timestamp_in_sec()
        event_settings = self.event_settings.get(event.get_type_identifier(), None)
        if event_settings is None:
            if isinstance(event, EvmEvent) is False:
                return 1

            # For evm events try to find settings without counterparty
            event_settings = self.event_settings.get(
                event.get_type_identifier(include_counterparty=False),
            )
            if event_settings is None:
                log.debug(
                    f'During transaction accounting found history base entry {event} '
                    f'with no mapped event settings. Skipping...',
                )
                return 1

        # if there is any module specific accountant functionality call it
        if (
            isinstance(event, EvmEvent) and
            isinstance(event_settings, TxEventSettings) and
            event_settings.accountant_cb is not None
        ):
            event_settings.accountant_cb(
                pot=self.pot,
                event=event,
                other_events=history_base_entries_iterator(events_iterator, event),
            )

        general_extra_data = {}
        if isinstance(event, EvmEvent):
            general_extra_data['tx_hash'] = event.tx_hash.hex()
        if event_settings.accounting_treatment in (TxAccountingTreatment.SWAP, TxAccountingTreatment.SWAP_WITH_FEE):  # noqa: E501

            fee_event = None
            if event_settings.accounting_treatment == TxAccountingTreatment.SWAP_WITH_FEE:
                fee_event = next(history_base_entries_iterator(events_iterator, event), None)
                if fee_event is None:
                    log.error(
                        f'Tried to process accounting swap but could not find '
                        f'the fee event for {event}',
                    )
                    return 1
            in_event = next(history_base_entries_iterator(events_iterator, event), None)
            if in_event is None:
                log.error(
                    f'Tried to process accounting swap but could not find the in '
                    f'event for {event}',
                )
                return 1

            return self._process_swap(
                timestamp=timestamp,
                out_event=event,
                in_event=in_event,
                fee_event=fee_event,
                event_settings=event_settings,
                general_extra_data=general_extra_data,
            )

        self.pot.add_asset_change_event(
            method=event_settings.method,
            event_type=AccountingEventType.TRANSACTION_EVENT,
            notes=event.notes if event.notes else '',
            location=event.location,
            timestamp=timestamp,
            asset=event.asset,
            amount=event.balance.amount,
            taxable=event_settings.taxable,
            count_entire_amount_spend=event_settings.count_entire_amount_spend,
            count_cost_basis_pnl=event_settings.count_cost_basis_pnl,
            extra_data=general_extra_data,
        )
        return 1

    def _process_swap(
            self,
            timestamp: Timestamp,
            out_event: HistoryBaseEntry,
            in_event: HistoryBaseEntry,
            fee_event: Optional[HistoryBaseEntry],
            event_settings: BaseEventSettings,
            general_extra_data: dict[str, Any],
    ) -> int:
        """
        Takes out_event (spend part), in_event (acquisition part), optionally fee part
        and generates corresponding accounting events.

        TODO: Contains similarities with Trade::process() which could be abstracted.
        Especially regarding the fees.
        """
        fee_info = None
        if fee_event is not None:
            fee_info = (fee_event.balance.amount, fee_event.asset)

        prices = self.pot.get_prices_for_swap(
            timestamp=timestamp,
            amount_in=in_event.balance.amount,
            asset_in=in_event.asset,
            amount_out=out_event.balance.amount,
            asset_out=out_event.asset,
            fee_info=fee_info,
        )
        if prices is None:
            log.debug(f'Skipping {self} at accounting for a swap due to inability to find a price')
            return 2

        consumed_events = 2

        group_id = out_event.event_identifier + str(out_event.sequence_index) + str(in_event.sequence_index)  # noqa: E501
        extra_data = general_extra_data | {'group_id': group_id}
        _, trade_taxable_amount = self.pot.add_spend(
            event_type=AccountingEventType.TRANSACTION_EVENT,
            notes=out_event.notes if out_event.notes else '',
            location=out_event.location,
            timestamp=timestamp,
            asset=out_event.asset,
            amount=out_event.balance.amount,
            taxable=event_settings.taxable,
            given_price=prices[0],
            count_entire_amount_spend=False,
            extra_data=extra_data,
        )
        if fee_event is not None:
            fee_price = None
            if fee_event.asset == self.pot.profit_currency:
                fee_price = Price(ONE)
            elif fee_event.asset == in_event.asset:
                fee_price = prices[1]
            elif fee_event.asset == out_event.asset:
                fee_price = prices[0]

            if self.pot.settings.include_fees_in_cost_basis:
                # If fee is included in cost basis, we just reduce the amount of fee asset owned
                fee_taxable = False
                fee_taxable_amount_ratio = ONE
            else:
                # Otherwise we make it a normal spend event
                fee_taxable = True
                fee_taxable_amount_ratio = trade_taxable_amount / out_event.balance.amount

            self.pot.add_spend(
                event_type=AccountingEventType.FEE,
                notes=fee_event.notes,  # type: ignore [arg-type]  # notes exist here
                location=fee_event.location,
                timestamp=timestamp,
                asset=fee_event.asset,
                amount=fee_event.balance.amount,
                taxable=fee_taxable,
                given_price=fee_price,
                # By setting the taxable amount ratio we determine how much of the fee
                # spending should be a taxable spend and how much free.
                taxable_amount_ratio=fee_taxable_amount_ratio,
                count_cost_basis_pnl=True,
                count_entire_amount_spend=True,
                extra_data=extra_data,
            )
            consumed_events = 3

        self.pot.add_acquisition(
            event_type=AccountingEventType.TRANSACTION_EVENT,
            notes=in_event.notes if in_event.notes else '',
            location=in_event.location,
            timestamp=timestamp,
            asset=in_event.asset,
            amount=in_event.balance.amount,
            taxable=False,  # acquisitions in swaps are never taxable
            given_price=prices[1],
            extra_data=extra_data,
        )
        return consumed_events
