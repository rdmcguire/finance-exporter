import re
import requests

class AlphaVantage:
    def __init__(self, api_key='demo', test=False):
        self.base       = 'https://www.alphavantage.co/query'
        self.api_key    = api_key
        self.payload = {
            'apikey': self.api_key
        }
        if test:
            ping = requests.get(self.base,params={'function':'GLOBAL_QUOTE','symbol':'NDAQ'})
            if ping.ok:
                print('>> AlphaVantage API Initialized OK')
            else:
                raise Exception(f'Unable to initialize AlphaVantage API {test.text}')

    def api_get(self):
        response = requests.get(self.base,params=self.payload)
        if response.ok:
            response = response.json()
            if response.get('Note') is not None:
                raise Exception('API Throttled...')
            return response
        else:
            raise Exception(f'API Request Failed: {response.text}')

    def method(self, method):
        self.payload['function'] = method

    def ticker(self, ticker):
        self.payload['symbol'] = ticker

    def get_quote(self):
        self.method('GLOBAL_QUOTE')
        quote = self.api_get()
        quote = quote.get('Global Quote')
        quote = {re.sub(r'\d+\.\s+(.*)', r'\1', k): v for k, v in quote.items()}
        return quote

    def get_overview(self):
        self.method('OVERVIEW')
        return self.api_get()

    def get_earnings(self,latest=True):
        self.payload['function'] = 'EARNINGS'
        earnings = self.api_get()
        if latest:
            earnings = earnings.get('quarterlyEarnings').pop(0)
        return earnings

    def get_all(self):
        info = dict()
        info.update(self.get_quote())
        info.update(self.get_overview())
        info.update(self.get_earnings())
        return info
