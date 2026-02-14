import pandas as pd
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.models.fee import MakerTakerFeeModel
from nautilus_trader.common.config import LoggingConfig
from nautilus_trader.core.datetime import dt_to_unix_nanos
from nautilus_trader.model import InstrumentId, Money, OrderBookDelta, TradeTick, QuoteTick, Venue
from nautilus_trader.model.currencies import USDT
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.model.enums import BookType

from strategies.order_placement_test_strategy import OrderPlacementTestStrategy, OrderPlacementTestStrategy_config


def configure_matching_test():
	start_date = "2025-11-21 13:42:59"
	end_date = "2025-11-22 00:00:00"
	instrument_name = '42USDT-PERP.BINANCE'

	# instruments_types = [(instrument_name, QuoteTick), (instrument_name, TradeTick)]
	instruments_types = [(instrument_name, QuoteTick)]

	config = OrderPlacementTestStrategy_config(instrument_id=InstrumentId.from_str(instrument_name),
											   subscription_type="deltas",
											   interval_ms=100,
											   snapshot_depth=1,
											   place_timestamp_ns=1763732580854000000,
											   place_timestamp_error_tolerance_ns=100000000,
											   order_side="BUY",
											   order_price=0.05457,
											   order_qty=100000)
	strategy = OrderPlacementTestStrategy(config=config)

	logging = LoggingConfig(log_level="INFO",
							log_level_file="INFO",
							log_directory='logs',
							log_file_max_backup_count=1000,
							log_colors=False)

	engine = BacktestEngine(config=BacktestEngineConfig(trader_id='matching-test', logging=logging))

	engine.add_strategy(strategy)

	engine.add_venue(venue=Venue('BINANCE'),
					 oms_type=OmsType.NETTING,
					 account_type=AccountType.MARGIN,
					 starting_balances=[Money(10000, USDT)],
					 fee_model=MakerTakerFeeModel(),
					 fill_model=None,
					 book_type=BookType.L2_MBP,
					 bar_execution=False,
					 trade_execution=True,
					 liquidity_consumption=True,
					 queue_position=True)

	catalog = ParquetDataCatalog(path='./catalog')

	start_ts = pd.Timestamp(start_date, tz="UTC")
	end_ts = pd.Timestamp(end_date, tz="UTC")

	start = dt_to_unix_nanos(start_ts)
	end = dt_to_unix_nanos(end_ts)

	instrument_names = list(set(instr_name for instr_name, data_type in instruments_types))
	instruments = catalog.instruments(instrument_ids=instrument_names)
	for instrument in instruments:
		engine.add_instrument(instrument)

	distinct_data_types = set(data_type for instr_name, data_type in instruments_types)
	for catalog_data_type in distinct_data_types:
		instrument_names = [instr_name for instr_name, data_type in instruments_types if data_type == catalog_data_type]
		data = catalog.query(data_cls=catalog_data_type, identifiers=instrument_names, start=start, end=end)
		engine.add_data(data)

	return engine


if __name__ == "__main__":
	engine = configure_matching_test()
	engine.run()
