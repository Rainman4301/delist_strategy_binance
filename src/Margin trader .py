"""
margin_trader.py

Consumes the delisting pairs identified by announcement_crawler.py and
opens isolated-margin short positions, sized by available USDT balance,
with stop-loss / take-profit rules based on the pair's first post-
announcement price bar.
"""

import logging
import os
from pathlib import Path

import pandas as pd
from binance.client import Client
from binance.enums import (
    ORDER_TYPE_LIMIT,
    SIDE_BUY,
    SIDE_SELL,
    TIME_IN_FORCE_GTC,
)
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
KLINES_DIR = BASE_DIR / "klines"
NEW_ANNOUNCEMENTS_PATH = DATA_DIR / "new_announcements.csv"


class MarginTrader:
    """Places isolated-margin short trades on freshly-announced delistings."""

    FIRST_BAR_LIMIT = 0.05   # max acceptable first-bar move before skipping a pair
    TAKE_PROFIT_PCT = 0.30
    SLIPPAGE_PCT = 0.001
    FEE_PCT = 0.001
    LEVERAGE = 3

    def __init__(self, pairs: list[str]):
        self.trade_list = list(pairs)
        self.trader = Client(*self._load_api_credentials())

        usdt_balance = float(self.trader.get_asset_balance(asset="USDT")["free"])
        self.trading_ratio = usdt_balance / max(len(self.trade_list), 1)

    @staticmethod
    def _load_api_credentials() -> tuple[str, str]:
        """Reads API credentials from environment variables.

        Store these in a local .env file (never committed — see .gitignore):
            BINANCE_API_KEY=...
            BINANCE_API_SECRET=...
        """
        api_key = os.environ.get("BINANCE_API_KEY")
        api_secret = os.environ.get("BINANCE_API_SECRET")
        if not api_key or not api_secret:
            raise RuntimeError(
                "Missing BINANCE_API_KEY / BINANCE_API_SECRET environment variables."
            )
        return api_key, api_secret

    def run(self) -> None:
        """Evaluates each pending pair once per loop and opens trades that qualify.

        NOTE: stop-loss / take-profit monitoring for open positions is not yet
        implemented (see the TODOs below) — this currently only handles trade
        entry, not exit.
        """
        loan_info: dict = {}
        sell_info: dict = {}

        while self.trade_list:
            for pair in list(self.trade_list):  # iterate over a copy — we mutate trade_list below
                klines_path = KLINES_DIR / f"{pair}_1m.csv"
                if not klines_path.exists():
                    logger.warning("No kline data for %s yet, skipping this cycle.", pair)
                    continue

                trade_data = pd.read_csv(klines_path)
                last_closed_price = trade_data.iloc[-1]["close"]
                current_price = float(self.trader.get_margin_price_index(symbol=pair)["price"])
                first_bar_change_pct = (current_price - last_closed_price) / last_closed_price
                tokens_affordable = self.trading_ratio // current_price

                if pair in loan_info:
                    if sell_info.get(pair, {}).get("status") == "FILLED":
                        self.trade_list.remove(pair)
                    continue

                # ---- Entry logic ----
                # If the first bar after the announcement drops (or is flat) within
                # FIRST_BAR_LIMIT, treat it as the start of the expected downtrend
                # and enter a short.
                if 0 <= first_bar_change_pct < self.FIRST_BAR_LIMIT:
                    logger.info("%s is in a downtrend — opening short.", pair)

                    loan_result = self.make_loan(pair, tokens_affordable)
                    loan_info[pair] = loan_result

                    if loan_result.get("tranId"):
                        logger.info("Loan for %s successful.", pair)
                        sell_result = self.sell_currency(pair, tokens_affordable)
                        sell_info[pair] = self.trader.get_margin_order(
                            symbol=pair, orderId=sell_result["orderId"], isIsolated="TRUE"
                        )
                        if sell_info[pair]["status"] == "FILLED":
                            self.trade_list.remove(pair)
                    else:
                        logger.warning("Loan for %s failed.", pair)

                elif first_bar_change_pct < 0:
                    # Price already moved up past our entry window before we could
                    # react — skip the pair rather than chase it.
                    # TODO: implement the "wait for a red candle, enter on next open"
                    # logic described in the original strategy notes if this proves
                    # too conservative in backtests.
                    logger.info("%s moved up before entry — skipping.", pair)
                    self.trade_list.remove(pair)

                # TODO: exit logic — check open positions in sell_info against
                # stop-loss / take-profit thresholds and close them here.

    def make_loan(self, pair: str, tokens_affordable: float) -> dict:
        """Transfers USDT into isolated margin and borrows the base asset to short."""
        self.trader.transfer_spot_to_margin(asset="USDT", amount=str(self.trading_ratio))

        max_loan = self.trader.get_max_margin_loan(asset=pair[:-4])
        leveraged_amount = tokens_affordable * self.LEVERAGE

        if leveraged_amount <= float(max_loan["amount"]):
            return self.trader.create_margin_loan(
                asset=pair[:-4], amount=str(leveraged_amount), isIsolated="TRUE", symbol=pair
            )
        return self.trader.create_margin_loan(
            asset=pair[:-4], amount=max_loan["amount"], isIsolated="TRUE", symbol=pair
        )

    def sell_currency(self, pair: str, amount: float) -> dict:
        return self.trader.create_margin_order(
            isIsolated="TRUE",
            symbol=pair,
            side=SIDE_SELL,
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=amount * self.LEVERAGE,
            price="0.00001",
            newOrderRespType="RESULT",
        )

    def buy_currency(self, pair: str, amount: float) -> dict:
        return self.trader.create_margin_order(
            isIsolated="TRUE",
            symbol=pair,
            side=SIDE_BUY,
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=amount * self.LEVERAGE,
            price="0.00001",
            newOrderRespType="RESULT",
        )

    def repay_loan(self, pair: str, amount: float) -> dict:
        return self.trader.repay_margin_loan(asset=pair, amount=str(amount * self.LEVERAGE))

    def cancel_order(self, pair: str, order_id: str) -> None:
        self.trader.cancel_margin_order(isIsolated="TRUE", symbol=pair, orderId=order_id)


if __name__ == "__main__":
    new_announcements = pd.read_csv(NEW_ANNOUNCEMENTS_PATH)
    pairs = [p.replace("/", "") for p in new_announcements["announcement_pair"].tolist()]

    if not pairs:
        logger.info("No new announcements to trade.")
    else:
        logger.info("Trading pairs: %s", pairs)
        MarginTrader(pairs).run()

        # clear the processed announcements without deleting the file
        new_announcements.iloc[0:0].to_csv(NEW_ANNOUNCEMENTS_PATH, index=False)