

import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
# from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup



import os
from datetime import datetime, timedelta
from binance.client import Client
from binance.enums import *


# import matplotlib.pyplot as plt
import pandas as pd
# import numpy as np


from binance.enums import SIDE_SELL, SIDE_BUY, ORDER_TYPE_MARKET

import margin_trade



class BinanceCrawler:
    def __init__(self, url):
        self.url = url
        self.driver = self.initialize_driver()
        self.df = pd.DataFrame(columns=['Anouncement_pair', 'Issued_date'])
        self.client = Client(self.api_key, self.api_secrete)

        


    def get_api_key(self):
        api_key_path = os.path.join(os.path.dirname(__file__), 'API_PUB.txt')
        api_secret_path = os.path.join(os.path.dirname(__file__), 'API_PRI.txt')
        with open(api_key_path, 'r') as file:
            api_key = file.read().replace('\n', '')
        with open(api_secret_path, 'r') as file:
            api_secret = file.read().replace('\n', '')
        return api_key, api_secret
    


    def initialize_driver(self):
        """Initializes the Selenium WebDriver."""
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-notifications")
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    def get_page_source(self, url):
        """Gets the page source for a given URL."""
        self.driver.get(url)
        return self.driver.page_source

    def parse_announcement_links(self):
        """Parses the announcement links from the main page."""
        html = self.get_page_source(self.url)
        soup = BeautifulSoup(html, 'html.parser')

        # Find the table with the announcements
        table = soup.find('div', {'class': 'css-1q4wrpt'})
        rows = table.find_all('div', {'class': 'css-1tl1y3y'})
        return rows

    def extract_announcement_details(self, row):
        """Extracts details from each announcement link."""
        title = row.find('div', {'class': 'css-1yxx6id'}).text
        if "Binance Will Delist" not in title:
            return None, None

        link = row.find('a')['href']
        issued_date = self.extract_issued_date(title)
        return link, issued_date

    def extract_issued_date(self, title):
        """Extracts the issued date from the announcement title."""
        title = (title[:-10] + ' ' + title[-10:]).replace(',', '').replace(' - ', ' ')
        title = title.split(' ')
        return title[-1]

    def fetch_filtered_pairs(self, link):
        """Fetches filtered trading pairs from the announcement page."""
        self.driver.execute_script(f"window.open('{link}', '_blank');")
        time.sleep(2)  # Wait for the new tab to load

        # Switch to the new tab
        self.driver.switch_to.window(self.driver.window_handles[1])
        html_nt = self.driver.page_source
        soup_nt = BeautifulSoup(html_nt, 'html.parser')

        # Find the announcement content
        table_nt = soup_nt.find('div', {'class': 'richtext-container css-fbxu07'})
        filtered_pairs = []
        if table_nt:
            all_text = table_nt.get_text(separator='\n', strip=True).split('\n')

            for item in all_text:
                if 'The exact trading pairs being removed are: ' in item:
                    pairs_string = item.split('The exact trading pairs being removed are: ')[1]
                    pairs_list = pairs_string.split(', ')
                    filtered_pairs = [pair for pair in pairs_list if pair.endswith('USDT')]
                    break


        # Close the tab and switch back
        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[0])
        return filtered_pairs

    def append_to_dataframe(self, filtered_pairs, issued_date):
        """Appends the filtered pairs and issued date to the DataFrame."""
        for pair in filtered_pairs:
            self.df = self.df._append({'Anouncement_pair': pair, 'Issued_date': issued_date}, ignore_index=True)





    def get_binance_data(self,symbol):
        

        

        #generate data folder
        if not os.path.exists("Data"):
            os.mkdir("Data")


        interval = Client.KLINE_INTERVAL_1MINUTE

        klines = self.client.get_historical_klines(symbol, interval ,klines_type=HistoricalKlinesType.SPOT, limit=5)

        # Convert the data to a pandas DataFrame for easier manipulation
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                                        'close_time', 'quote_asset_volume', 'number_of_trades', 
                                        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])

        # Convert timestamp to readable date
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')


        with open(f'DATA/{symbol}_1m.csv', 'w',newline="") as file:
            df.to_csv(file, index=False)



    def compare_and_update_data(self):
        """Compares new and old data, and updates the CSV file."""
        try:

            old_data_path = os.path.join(os.path.dirname(__file__), './bulletin_data/old_announcements.csv')
            old_data = pd.read_csv(old_data_path)


        except FileNotFoundError:
            old_data = pd.DataFrame(columns=['Anouncement_pair', 'Issued_date'])

        new_announcements = self.df[~self.df['Anouncement_pair'].isin(old_data['Anouncement_pair'])]

        if not new_announcements.empty:

            for pair in new_announcements['Anouncement_pair']:

                pair = pair.replace('/', '')
                print(f"new announcement found for {pair}")
                # self.get_binance_data(pair)

            

            new_announcements.to_csv('./bulletin_data/new_announcements.csv', index=False)
            new_data = pd.concat([new_announcements, old_data], ignore_index=True)
            new_data.to_csv('./bulletin_data/old_announcements.csv', index=False)
            print('New announcements found and saved to old_announcements.csv')

        else:
            print('No new announcements found')







        



    



    def run(self):
        """Main method to run the crawler."""
        rows = self.parse_announcement_links()

        for row in rows:
            link, issued_date = self.extract_announcement_details(row)
            if link and issued_date:
                filtered_pairs = self.fetch_filtered_pairs(link)
                self.append_to_dataframe(filtered_pairs, issued_date)

                break

        self.compare_and_update_data()

        # Close the browser
        self.driver.quit()








if __name__ == '__main__':


    annota_time = []

    for i in range(1):

        #count the time
        start_time = time.time()

        url = 'https://www.binance.com/en/support/announcement/delisting?c=161&navId=161'
        binance_crawler = BinanceCrawler(url)
        binance_crawler.run()

        annota_time.append(time.time() - start_time)






















    # # plot the average time distribution 

    # average_time = np.array(annota_time).mean()
    # variance_time = np.var(annota_time)

    # print(f"Average time: {average_time}")
    # print(f"Variance time: {variance_time}")

    # # plot the average time distribution 
    # plt.hist(annota_time, bins=10)
    # plt.xlabel('Time')
    # plt.ylabel('Frequency')
    # plt.title('Time Distribution')
    # plt.show()

    # with open ('time_series.txt', 'w') as file:
    #     for time in annota_time:
    #         file.write(f"{time}\n")




    


        

        


    
