from nautilus_trader.backtest.config import FeeModelConfig
from nautilus_trader.backtest.models.fee import FeeModel
from nautilus_trader.core.rust.model import LiquiditySide
from nautilus_trader.model.functions import liquidity_side_to_str
from nautilus_trader.model.instruments.base import Instrument
from nautilus_trader.model.objects import Money
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity
from nautilus_trader.model.orders.base import Order

class MakerTakerFeeModel_AdjustableConfig(FeeModelConfig, frozen=True):
	maker_fee: str
	taker_fee: str

class MakerTakerFeeModel_Adjustable(FeeModel):
	def __init__(self, config = None) -> None:
		if config is None:
			raise Exception("No config for MakerTakerFeeModel_Adjustable")

		if config is not None:
			# Initialize from config
			self._maker_fee = float(config.maker_fee)
			self._taker_fee = float(config.taker_fee)

			# Negative maker fee is possible - rebate
			if self._maker_fee is None or self._taker_fee is None or self._taker_fee < 0:
				raise Exception(f"Provide correct maker and taker fee values. Provided values: {self._maker_fee=}, {self._taker_fee=}")

	def get_commission(self, order: Order, fill_qty: Quantity, fill_px: Price, instrument: Instrument):
		notional = instrument.notional_value(
			quantity=fill_qty,
			price=fill_px,
			use_quote_for_inverse=False,
		)

		if order.liquidity_side == LiquiditySide.MAKER:
			commission_f64 = notional * self._maker_fee
		elif order.liquidity_side == LiquiditySide.TAKER:
			commission_f64 = notional * self._taker_fee
		else:
			raise ValueError(
				f"invalid `LiquiditySide`, was {liquidity_side_to_str(order.liquidity_side)}"
			)

		if instrument.is_inverse:  # Not using quote for inverse (see above):
			commission = Money(commission_f64, instrument.base_currency)
		else:
			commission = Money(commission_f64, instrument.quote_currency)

		return commission