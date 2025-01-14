

from binance.client import Client


# -------------- client -----------------
client = Client(key_content, secret_content)


# client.create_isolated_margin_account(symbol='BTCUSDT')
def open_marin_account(symbol, amount):
    transaction = client.transfer_spot_to_isolated_margin(asset='USDT',
                                                            symbol=symbol, amount=amount)
    # transaction = client.transfer_isolated_margin_to_spot(asset='USDT',
    #                                                         symbol=symbol, amount=amount)

    original_string = symbol
    symbol_without_usdt = original_string.replace('USDT', '')

    details = client.get_max_margin_loan(asset=symbol_without_usdt, isolatedSymbol=symbol)
    return details


def loan(symbol, symbol_amount):
    original_string = symbol
    symbol_without_usdt = original_string.replace('USDT', '')

    transaction = client.create_margin_loan(asset=symbol_without_usdt, amount=symbol_amount, isIsolated='TRUE', Symbol=symbol)
    print('已借款', transaction)



# ---------------------- Setting --------------------------
token_symbol = 'APTUSDT'
usdt_amount = 10
leverage = 3
original_string = token_symbol
symbol_without_usdt = original_string.replace('USDT', '')
print(symbol_without_usdt)

# ---------------------- Open Account --------------------------
result = open_marin_account(token_symbol, usdt_amount)

print('開設帳戶成功')

klines = client.get_historical_klines(token_symbol, Client.KLINE_INTERVAL_1MINUTE, limit=1)
data = pd.DataFrame(klines)
close_price = float( data.iloc[0, 4] )
print(f'{token_symbol}現在價格為 :{close_price}')
#----------
symbol_amount = usdt_amount//close_price
print('symbol_amount : ', symbol_amount)
amount_after_leverage = symbol_amount * leverage
print('amount_after_leverage : ', amount_after_leverage)
# ---------------------- Loan --------------------------
loan(token_symbol, amount_after_leverage)

print('借款成功')
# ---------------------- Place Order --------------------------

order = client.create_margin_order(
    symbol=token_symbol,
    isIsolated = 'True',
    side=SIDE_SELL,
    type=ORDER_TYPE_MARKET,
    # timeInForce=TIME_IN_FORCE_GTC,
    quantity=amount_after_leverage
    # price=9
    )

# ---------------------- Put SL/TP --------------------------

# sl_order = client.create_margin_order(
#     symbol=token_symbol,
#     isIsolated = 'True',
#     side=SIDE_BUY,
#     type=ORDER_TYPE_STOP_LOSS,
#     # timeInForce=TIME_IN_FORCE_GTC,
#     quantity=amount_after_leverage,
#     stopPrice=9,
#     # price=9.19
#     )

# tp_order = client.create_margin_order(
#     symbol=token_symbol,
#     isIsolated = 'True',
#     side=SIDE_BUY,
#     type=ORDER_TYPE_TAKE_PROFIT_LIMIT,
#     timeInForce=TIME_IN_FORCE_GTC,
#     quantity=amount_after_leverage,
#     stopPrice = 4,
#     price=4.1)

# ---------------------- OCO --------------------------

# 假設時間到要close position的話，必須先把訂單取消掉。
oco_order = client.create_margin_oco_order(
    symbol='ATMUSDT',
    isIsolated = 'True',
    side=SIDE_BUY,
    quantity = 1400,
    stopPrice = 2.411,
    price = 1.788,
    sideEffectType = 'AUTO_REPAY'
    )

# ---------------------- Futures OCO --------------------------

# 假設時間到要close position的話，必須先把訂單取消掉。
# TAKE_PROFIT_LIMIT order (modify this)
take_profit_limit = client.futures_create_order(
    symbol='DIAUSDT',
    side=SIDE_BUY,
    type=ORDER_TYPE_LIMIT,
    quantity=4161,
    timeInForce='GTC',
    price=0.7108,
    reduceOnly=True  # 僅用於平倉
)

# STOP_MARKET order
stop_market = client.futures_create_order(
    symbol='DIAUSDT',
    side=SIDE_BUY,
    quantity = 3421,
    type=FUTURE_ORDER_TYPE_STOP_MARKET,
    stopPrice=0.9227,       # Specify the trigger price
    reduceOnly=True
    
)


# ---------------------- Buy Back --------------------------

# order = client.create_margin_order(2.08
#     symbol=token_symbol,
#     isIsolated = 'True',
#     side=SIDE_BUY,
#     type=ORDER_TYPE_MARKET,
#     # timeInForce=TIME_IN_FORCE_GTC,
#     quantity=amount_after_leverage
#     # price=9
#     )

# ---------------------- Repay --------------------------

transaction = client.repay_margin_loan(asset='FTT', amount=1, isIsolated='TRUE', Symbol='FTTUSDT')
transaction = client.transfer_isolated_margin_to_spot(asset='USDT', symbol='APTUSDT', amount=0.95192464)