
from binance.client import Client 
from binance.enums import *
import os
import pandas as pd
from datetime import datetime





class MarginTrade:
    def __init__(self,pairs):
        self.trade_list = pairs

        self.api_key, self.api_secrete = self.get_api_key()
        self.trader = Client(self.api_key, self.api_secrete)

        self.first_bar_limit = 0.05
        self.tp_point = 0.3
        self.slippage = 0.001
        self.fee = 0.001

        self.trading_ration = self.trader.get_asset_balance(asset='USDT')// len(self.trade_list)
        

        

    def get_api_key(self):
        api_key_path = os.path.join(os.path.dirname(__file__), 'API_PUB.txt')
        api_secret_path = os.path.join(os.path.dirname(__file__), 'API_PRI.txt')
        with open(api_key_path, 'r') as file:
            api_key = file.read().replace('\n', '')
        with open(api_secret_path, 'r') as file:
            api_secret = file.read().replace('\n', '')
        return api_key, api_secret


    def run(self):
        

        # Dictionary to store the start times of trades
        loan_info = {}
        sell_info = {}
        buy_info = {}
        stop_loss_info ={}
        
        


        while self.trade_list or loan_info:

            for pair in self.trade_list:

                trade_data = pd.read_csv(f'DATA/{pair}_1m.csv') 

                # get the last row of the closed data
                last_closed_data = trade_data.loc[trade_data.index[-1], 'close']
                #get the current price of the pair from binance
                current_price = float(self.trader.get_margin_price_index(symbol=pair)['price'])
                # calculate the percentage of change from the last closed data
                start_bar_per = (current_price - last_closed_data )/last_closed_data
                number_token_could_buy = self.trading_ration // current_price


                
            

                if pair not in loan_info:

                    # ------------------------------進場邏輯------------------------------
                    # 假設第一根沒有超過 first_bar_limit 的限制，且第一根的方向是向下或是等於零的話進場
                    # price going down(make the short)
                    if  start_bar_per < self.first_bar_limit and start_bar_per >= 0:
                        print(f'{pair} is in a downtrend')


                        # set the stop loss and take profit levels
                        # 若第一根K棒為幅度0，則停損我上調 4% = 1.0297 * 1.01 
                        # 為何是乘 1.0297，是因為之後的停損是 first_bar_open_price * 1.01 ，因此將 first_bar_open_price * 1.0297
                        if start_bar_per == 0:
                            last_closed_data = last_closed_data * 1.0297


                        loan_result = self.make_loan(pair,number_token_could_buy)
                        loan_info[pair] = loan_result


                        if loan_info[pair]["tranId"] :
                            print(f"The loan for {pair} is successful")
                            sell_result = self.sell_currency()

                            sell_info[pair] = self.trader.get_margin_order(symbol=pair, orderId=sell_result["orderId"], isIsolated='TRUE')

                            if sell_info[pair]["status"] == "FILLED":
                                self.trade_list.remove(pair)
                            else:
                                pass
                        else:
                            print(f"The loan for {pair} is not successful")


                    # 假設第一根的方向是向上的話，等待 TK 進場，但會有兩種情況：
                    # 1. 等k棒變紅k，收盤價低於前一根綠k的開盤價，則下一根K棒開盤價進場。
                    # 2. 等k棒變紅k，收盤價低於前一根紅k的收盤價，則下一根K棒開盤價進場。
                    # price going up(make the long)
                    elif start_bar_per < 0:


                        # remove this pair from self.trade_list
                        self.trade_list.remove(pair)
                        

                        """

                        print(f'{pair} is in an uptrend')

                        last_df = self.get_last_1M_data(pair)

                        previous_bar_open = last_df["open"].values[0]
                        previous_bar_close = last_df["close"].values[0]
                        current_price = float(self.trader.get_margin_price_index(symbol=pair)['price']) 
                        



                        # if last bar is red bar
                        if previous_bar_open > previous_bar_close:
                            if current_price < previous_bar_close and (previous_bar_close - current_price)/previous_bar_close < self.first_bar_limit:
                                
                                #重新設置停損點，因第一根k棒是漲起來的，以至於停損點會變動。
                                
                                # ( make the short ) 
                                # (1) loan the currency

                                loan_info = self.make_loan()

                                if loan_info["status"] == "filled":

                                    trade_info[pair] = loan_info
                                    self.trade_list.remove(pair)
                                else:
                                    pass
                        


                                # (2) buy short the currency

                        

                        # if last bar is green bar
                        elif previous_bar_open < previous_bar_close:
                            if current_price < previous_bar_open and (previous_bar_close - current_price)/previous_bar_close < self.first_bar_limit:
            
                                #重新設置停損點，因圓心第一根k棒是漲起來的，以至於停損點會變動。
                                
                                # ( make the short ) 
                                # (1) loan the currency

                                loan_info = self.make_loan()

                                if loan_info["status"] == "filled":

                                    trade_info[pair] = loan_info
                                    self.trade_list.remove(pair)
                                else:
                                    pass
                        
                    

                                # (2) buy short the currency

                        else:
                            print("Doesn't meet the conditions to enter the market")
                            
                        
                        """
                else:
                    if sell_info[pair]["status"] == "FILLED":
                        self.trade_list.remove(pair)
                    else:
                        pass


                # ------------------------------出場邏輯(包括停損)------------------------------


                # Monitor existing trades to see if 6 hours have passed
                if pair in sell_info:
                    
                    # Stop loss check
                    pass

                    # Take profit check

                else:
                    pass

                
                
                           


    def make_loan(self, pair, number_token_could_buy):

        # ( make the short ) 
        #(1) transfer money from spot to margin 
        transaction = self.trader.transfer_spot_to_margin(asset='USDT', amount=str(self.trading_ration))


        # (2) loan the currencyv
        details = self.trader.get_max_margin_loan(asset=pair[:-4])
        if number_token_could_buy*3 <= float(details['amount']):
            transaction = self.trader.create_margin_loan(asset=pair[:-4], amount=str(number_token_could_buy*3), isIsolated='TRUE', symbol=pair)
        else:   
            transaction = self.trader.create_margin_loan(asset=pair[:-4], amount=details['amount'], isIsolated='TRUE', symbol=pair)

        
        return transaction




    def sell_currency(self, pair, amount):

        order = self.trader.create_margin_order(
            isIsolated ="TRUE",
            symbol=pair,
            side=SIDE_BUY,
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=amount*3,
            price='0.00001',
            newOrderRespType = "RESULT")
        
        return order
    
    def buy_currency(self, pair, amount):
            
        order = self.trader.create_margin_order(
            isIsolated ="TRUE",
            symbol=pair,
            side=SIDE_SELL,
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=amount*3,
            price='0.00001',
            newOrderRespType = "RESULT")
        
        return order

    def repay_loan(self, pair,amount):
        transaction = self.trader.repay_margin_loan(asset=pair, amount=str(amount*3))

        return transaction
        

    def close_trade(self, pair):
        pass


    def cancel_order(self,pair):
        result = self.trader.cancel_margin_order(
                isIsolated = "TRUE" ,
                symbol=pair,
                orderId='orderId')



    

    def get_last_1M_data(self, pair):
        klines = self.trader.get_historical_klines(pair, Client.KLINE_INTERVAL_1MINUTE, klines_type=HistoricalKlinesType.SPOT , limit = 1)

        # Convert the data to a pandas DataFrame for easier manipulation
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                                        'close_time', 'quote_asset_volume', 'number_of_trades', 
                                        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])

        return df
                
                    
    
        

if __name__ == "__main__":

    #read the new_announcement.csv file check if there is any new announcement

    new_announcement = pd.read_csv('./bulletin_data/new_announcements.csv')
    pair_list = new_announcement['Anouncement_pair'].tolist()
    pair_list = list(map(lambda pair: pair.replace('/', ''), pair_list))
    

    #if there is any new announcement, then run the trade
    if pair_list == []:
        print("There is no new announcement")
        

    else:
        
        trade = MarginTrade(pair_list)
        # trade.run()
        print(pair_list)

        # clean the new_announcement.csv data without deleting the file
        new_announcement.drop(new_announcement.index, inplace=True)
        new_announcement.to_csv('./bulletin_data/new_announcements.csv', index=False)
    


    # clean all the file from Data directory 



    

    
