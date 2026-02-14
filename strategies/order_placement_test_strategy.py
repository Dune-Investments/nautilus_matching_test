from __future__ import annotations
from typing import Literal

import pandas as pd
from nautilus_trader.core.data import Data
from nautilus_trader.model.data import OrderBookDelta, OrderBookDeltas, OrderBookDepth10, TradeTick, QuoteTick
from nautilus_trader.model.book import OrderBook
from nautilus_trader.model import InstrumentId
from nautilus_trader.model.enums import BookType, OrderSide, TimeInForce
from nautilus_trader.model.events.order import OrderFilled
from nautilus_trader.trading.config import StrategyConfig
from nautilus_trader.trading.strategy import Strategy


class OrderPlacementTestStrategy_config(StrategyConfig):
	instrument_id: InstrumentId
	subscription_type: Literal['snapshot', 'delta', 'quote']
	interval_ms: int
	snapshot_depth: int
	place_timestamp_ns: int
	place_timestamp_error_tolerance_ns: int
	order_side: Literal['BUY', 'SELL']
	order_price: float
	order_qty: float


class OrderPlacementTestStrategy(Strategy):
	def __init__(self, config: OrderPlacementTestStrategy_config) -> None:
		"""Initialise all runtime structures, guards, and cached config values."""
		super().__init__(config=config)
		self.instr_id = config.instrument_id

		self.init_config = config
		self.step_ns = config.interval_ms * 1000 * 1000
		self.last_update_ts = 0

		self.order_sent = False
		self.filled_ts = None
		self.rows = []

	def on_start(self) -> None:
		"""Load instrument metadata, reconcile state, and subscribe to feeds."""
		self.instr = self.cache.instrument(self.instr_id)
		self.lot = float(self.instr.lot_size)
		self.tick = float(self.instr.price_increment)

		if self.init_config.subscription_type == 'snapshot':
			self.subscribe_order_book_at_interval(instrument_id=self.instr.id,
												  book_type=BookType.L2_MBP,
												  depth=5,
												  interval_ms=self.init_config.interval_ms,
												  params=None)

			self.subscribe_order_book_depth(instrument_id=self.instr.id, book_type=BookType.L2_MBP, depth=5)

			self.subscribe_order_book_deltas(self.instr.id, BookType.L2_MBP)
		elif self.init_config.subscription_type == 'quote':
			self.subscribe_quote_ticks(self.instr.id)
		else:  # 'delta'
			self.subscribe_order_book_deltas(self.instr.id, BookType.L2_MBP)

		self.subscribe_trade_ticks(self.instr.id)

	def on_order_book_deltas(self, deltas: OrderBookDeltas) -> None:
		"""Process incoming L2 delta, honoring rate limits and invoking core logic."""
		# if self.step_ns > 0 and (order_book_delta.ts_event - self.last_update_ts) < self.step_ns:
		# 	return
		book = self.cache.order_book(deltas.instrument_id)

		for delta in deltas.deltas:
			row = {
					'UPDATE_TYPE'       : 'Delta',
					'LOCAL_TIMESTAMP'   : deltas.ts_init,
					'EXCHANGE_TIMESTAMP': deltas.ts_event,
					'CLIENT_ORDER_ID'   : None,
					'VENUE_ORDER_ID'    : delta.order.order_id,
					'PAIR'              : self.instr.symbol.value,
					'SIDE'              : delta.order.side.name,
					'PRICE'             : delta.order.price.as_double(),
					'QTY'               : delta.order.size.as_double(),
					'FILLED_QTY'        : None,
					'ORDER_TYPE'        : None,
					'ORDER_STATUS'      : None,
					'DELTA_ACTION'      : delta.action.name,
					'DELTA_SEQUENCE'    : deltas.sequence,
					'BOOK_BID'          : book.best_bid_price().as_double() if book.best_bid_price() else 0,
					'BOOK_BID_SIZE'		: book.best_bid_size().as_double() if book.best_bid_size() else 0,
					'BOOK_ASK'          : book.best_ask_price().as_double() if book.best_ask_price() else 0,
					'BOOK_ASK_SIZE'		: book.best_ask_size().as_double() if book.best_ask_size() else 0,
					}
			self.rows.append(row)

		self.run_core(delta, book)
		self.last_update_ts = delta.ts_event

	def on_trade_tick(self, tick: TradeTick) -> None:
		book = self.cache.order_book(tick.instrument_id)

		if book is not None:
			book_bid = book.best_bid_price().as_double() if book.best_bid_price() else 0
			book_ask = book.best_ask_price().as_double() if book.best_ask_price() else 0
			book_bid_size = book.best_bid_price().as_double() if book.best_bid_price() else 0
			book_ask_size = book.best_bid_size().as_double() if book.best_bid_size() else 0
		else:
			book_bid = 0
			book_ask = 0
			book_bid_size = 0
			book_ask_size = 0

		row = {
				'UPDATE_TYPE'       : 'TradeTick',
				'LOCAL_TIMESTAMP'   : tick.ts_init,
				'EXCHANGE_TIMESTAMP': tick.ts_event,
				'CLIENT_ORDER_ID'   : None,
				'VENUE_ORDER_ID'    : None,
				'PAIR'              : self.instr.symbol.value,
				'SIDE'              : tick.aggressor_side.name,
				'PRICE'             : tick.price.as_double(),
				'QTY'               : tick.size.as_double(),
				'FILLED_QTY'        : tick.size.as_double(),
				'ORDER_TYPE'        : None,
				'ORDER_STATUS'      : None,
				'DELTA_ACTION'      : None,
				'DELTA_SEQUENCE'    : None,
				'BOOK_BID'          : book_bid,
				'BOOK_BID_SIZE': book_bid_size,
				'BOOK_ASK'          : book_ask,
				'BOOK_ASK_SIZE'		: book_ask_size,
				}
		self.rows.append(row)

	def on_order_event(self, event):
		order = self.cache.order(event.client_order_id)
		if not order: return

		book = self.cache.order_book(event.instrument_id)

		if book is not None:
			book_bid = book.best_bid_price().as_double() if book.best_bid_price() else 0
			book_ask = book.best_ask_price().as_double() if book.best_ask_price() else 0
			book_bid_size = book.best_bid_price().as_double() if book.best_bid_price() else 0
			book_ask_size = book.best_bid_size().as_double() if book.best_bid_size() else 0
		else:
			book_bid = 0
			book_ask = 0
			book_bid_size = 0
			book_ask_size = 0

		row = {
				'UPDATE_TYPE'       : 'MyOrder',
				'LOCAL_TIMESTAMP'   : event.ts_init,
				'EXCHANGE_TIMESTAMP': event.ts_event,
				'CLIENT_ORDER_ID'   : event.client_order_id,
				'VENUE_ORDER_ID'    : event.venue_order_id,
				'PAIR'              : event.instrument_id.symbol,
				'SIDE'              : order.side.name,
				'PRICE'             : float(order.price) if hasattr(order, 'price') else None,
				'QTY'               : order.quantity.as_double(),
				'FILLED_QTY'        : order.filled_qty.as_double(),
				'ORDER_TYPE'        : order.order_type.name,
				'ORDER_STATUS'      : order.status.name,
				'DELTA_ACTION'      : type(event).__name__,
				'DELTA_SEQUENCE'    : None,
				'BOOK_BID'          : book_bid,
				'BOOK_BID_SIZE'		: book_bid_size,
				'BOOK_ASK'          : book_ask,
				'BOOK_ASK_SIZE'		: book_ask_size,
				}
		self.rows.append(row)

		if isinstance(event, OrderFilled) and order.quantity == order.filled_qty:
			self.log.info(f'Order {event.client_order_id} {event} has been filled. Will exit shortly.')
			self.filled_ts = event.ts_event

	def on_order_book(self, order_book: OrderBook) -> None:

		self.run_core(order_book, order_book)

	def on_order_book_depth(self, depth: OrderBookDepth10):
		pass

	def run_core(self, data: Data, book: OrderBook) -> None:

		t = data.ts_event

		if (self.filled_ts is not None and abs(self.filled_ts - t) >= 5 * 1000 * 1000 * 1000):
			df = pd.DataFrame(self.rows)
			df.to_csv(f'updates_{self.trader_id.value}.csv', index=False)
			self.stop()
			return

		if self.order_sent:
			return

		if not book.spread():
			return

		bid = book.best_bid_price()
		ask = book.best_ask_price()

		if (abs(t - self.init_config.place_timestamp_ns) < self.init_config.place_timestamp_error_tolerance_ns):
			cur_pos = self.portfolio.net_position(self.instr_id)

			if cur_pos != 0:
				self.log.info(f'Current pos={cur_pos}. Will not trade again')
				return

			price = self.instr.make_price(self.init_config.order_price)
			side = OrderSide.BUY if self.init_config.order_side.upper() == 'BUY' else OrderSide.SELL
			if (price >= ask and side == OrderSide.BUY) or (price <= bid and side == OrderSide.SELL):
				self.log.info(f'{price=} {bid=} {ask=}. Will not trade.')
				return

			order = self.order_factory.limit(instrument_id=self.instr_id,
											 order_side=side,
											 price=price,
											 quantity=self.instr.make_qty(self.init_config.order_qty),
											 time_in_force=TimeInForce.GTC)
			self.submit_order(order)
			self.order_sent = True

	def on_quote_tick(self, tick: QuoteTick) -> None:
		"""Process incoming quote tick data."""
		row = {
			'UPDATE_TYPE'       : 'QuoteTick',
			'LOCAL_TIMESTAMP'   : tick.ts_init,
			'EXCHANGE_TIMESTAMP': tick.ts_event,
			'CLIENT_ORDER_ID'   : None,
			'VENUE_ORDER_ID'    : None,
			'PAIR'              : self.instr.symbol.value,
			'SIDE'              : None,
			'PRICE'             : None,
			'QTY'               : None,
			'FILLED_QTY'        : None,
			'ORDER_TYPE'        : None,
			'ORDER_STATUS'      : None,
			'DELTA_ACTION'      : None,
			'DELTA_SEQUENCE'    : None,
			'BOOK_BID'          : tick.bid_price.as_double(),
			'BOOK_BID_SIZE'		: tick.bid_size.as_double(),
			'BOOK_ASK'          : tick.ask_price.as_double(),
			'BOOK_ASK_SIZE'		: tick.ask_size.as_double()
		}
		self.rows.append(row)

		self.run_core_quote(tick)

	def run_core_quote(self, tick: QuoteTick) -> None:
		"""Core logic for quote tick data (no OrderBook object)."""
		t = tick.ts_event

		if (self.filled_ts is not None and abs(self.filled_ts - t) >= 5 * 1000 * 1000 * 1000):
			df = pd.DataFrame(self.rows)
			df.to_csv(f'updates_{self.trader_id.value}.csv', index=False)
			self.stop()
			return

		if self.order_sent:
			return

		bid = tick.bid_price
		ask = tick.ask_price

		# Check spread exists (bid and ask are valid)
		if not bid or not ask or bid >= ask:
			return

		if (abs(t - self.init_config.place_timestamp_ns) < self.init_config.place_timestamp_error_tolerance_ns):
			cur_pos = self.portfolio.net_position(self.instr_id)

			if cur_pos != 0:
				self.log.info(f'Current pos={cur_pos}. Will not trade again')
				return

			price = self.instr.make_price(self.init_config.order_price)
			side = OrderSide.BUY if self.init_config.order_side.upper() == 'BUY' else OrderSide.SELL
			if (price >= ask and side == OrderSide.BUY) or (price <= bid and side == OrderSide.SELL):
				self.log.info(f'{price=} {bid=} {ask=}. Will not trade.')
				return

			order = self.order_factory.limit(instrument_id=self.instr_id,
											 order_side=side,
											 price=price,
											 quantity=self.instr.make_qty(self.init_config.order_qty),
											 time_in_force=TimeInForce.GTC)
			self.submit_order(order)
			self.order_sent = True
