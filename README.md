# Binance Delisting Strategy

An automated pipeline that detects Binance delisting announcements and opens risk-managed short positions on the affected pairs, capturing the price drop that typically follows a delisting notice.

## How it works

1. **Announcement Crawler** (`src/announcement_crawler.py`) — scrapes Binance's delisting board with Selenium, extracts the affected trading pairs, and diffs them against previously-seen announcements so only new events trigger a trade.
2. **Margin Trader** (`src/margin_trader.py`) — sizes each position from available USDT balance, opens an isolated-margin short via the Binance API, and applies stop-loss / take-profit rules based on the pair's price action right after the announcement.

```
Announcement detected → price checked against last close → short opened → SL/TP managed
```

## Tech stack

`Python` · `python-binance` · `Selenium` · `BeautifulSoup` · `pandas`

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # add your Binance API key/secret
python src/announcement_crawler.py
python src/margin_trader.py
```

## Project status

Entry logic and risk sizing are implemented and tested against historical announcement data. Exit-side stop-loss/take-profit monitoring is in progress — see `TODO`s in `margin_trader.py`.

## Disclaimer

Built for research and learning purposes. Not financial advice; use at your own risk.
