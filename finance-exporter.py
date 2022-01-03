#!/usr/bin/python3
import argparse
import time
from datetime import datetime
import sys
import yaml
import yfinance as yf
from prometheus_client import start_http_server, Counter, Gauge, Summary, Histogram
from includes.alphavantage import AlphaVantage

class finance:

    def __init__(self, args):
        # Prepare the config
        self.config = dict()
        self.load_config(args.config)
        # Set up -- prefer command line arg to yaml arg
        self.verbose            = args.verbose
        self.config['port']     = next(v for v in [ args.port, self.config.get('port') ] if v is not None)
        self.config['address']  = next(v for v in [ args.address, self.config.get('address') ] if v is not None)
        self.config['interval'] = next(v for v in [ args.interval, self.config.get('interval') ] if v is not None)
        self.labels             = list(self.config['labels'].keys())
        self.metrics            = list(self.config['metrics'].keys())
        # Setup plugin. Default plugin is yfinance
        self.plugin             = next(v for v in [ self.config.get('plugin'), 'yfinance' ] if v is not None)
        if self.plugin == 'alphavantage' and self.config.get('api_key') is None:
            self.print_log('Must provide API Key for AlphaVantage to use plugin')
            sys.exit(1)
        elif self.plugin == 'alphavantage':
            self.av = AlphaVantage(self.config.get('api_key'))
        # Prometheus Metrics
        self.prom_metrics               = dict()
        self.prom_metrics['updates']    = Counter(f"{self.config['metric_prefix']}_updates", 'Number of ticker updates', self.labels)
        self.prom_metrics['quote_time'] = Gauge(f"{self.config['metric_prefix']}_quote_time", 'Time spent retrieving quote', self.labels)
        # Prepare metrics
        for metric in self.metrics:
            if self.config['metrics'][metric]['type'] == 'Counter':
                self.prom_metrics[metric] = Counter(f"{self.config['metric_prefix']}_{metric}", self.config['metrics'][metric]['help'], self.labels)
            elif self.config['metrics'][metric]['type'] == 'Gauge':
                self.prom_metrics[metric] = Gauge(f"{self.config['metric_prefix']}_{metric}", self.config['metrics'][metric]['help'], self.labels)
            elif self.config['metrics'][metric]['type'] == 'Histogram':
                self.prom_metrics[metric] = Histogram(f"{self.config['metric_prefix']}_{metric}", self.config['metrics'][metric]['help'], self.labels)
            elif self.config['metrics'][metric]['type'] == 'Summary':
                self.prom_metrics[metric] = Summary(f"{self.config['metric_prefix']}_{metric}", self.config['metrics'][metric]['help'], self.labels)

    def load_config(self, config_file):
        with open(config_file, 'r') as config_file:
            self.config = yaml.load(config_file, Loader=yaml.FullLoader)

    def print_config(self):
        self.print_log(self.config)

    def start_server(self):
        if self.verbose:
            self.print_log(f"Starting HTTP Server on {self.config['address']}:{self.config['port']}")
        start_http_server(int(self.config['port']), addr=self.config['address'])

    def fetch_data(self, ticker):
        if self.plugin == 'yfinance':
            return yf.Ticker(ticker).info
        elif self.plugin == 'alphavantage':
            self.av.ticker(ticker)
            return self.av.get_all()

    def update(self):
        for ticker in self.config['tickers']:
            if self.verbose:
                self.print_log(f'Updating ticker {ticker}')
            start_time = time.time()
            try:
                quote = self.fetch_data(ticker)
            except Exception as e:
                print(f'Error fetching {ticker}: {e}')
                continue
            duration = time.time() - start_time
            quote_info = dict()
            # Update label values
            for label in self.labels:
                quote_info[label] = quote.get(self.config['labels'][label])
            # Update Manual Metrics
            self.prom_metrics['updates'].labels(**quote_info).inc()
            self.prom_metrics['quote_time'].labels(**quote_info).set(duration)
            # Update Configured Metrics
            for metric in self.metrics:
                value = quote.get(self.config['metrics'][metric]['item'])
                if value is None:
                    continue
                if self.config['metrics'][metric]['type'] == 'Counter':
                    self.prom_metrics[metric].labels(**quote_info).inc()
                elif self.config['metrics'][metric]['type'] == 'Gauge':
                    self.prom_metrics[metric].labels(**quote_info).set(value)
                elif self.config['metrics'][metric]['type'] == 'Histogram':
                    self.prom_metrics[metric].labels(**quote_info).observe(value)
                elif self.config['metrics'][metric]['type'] == 'Summary':
                    self.prom_metrics[metric].labels(**quote_info).observe(value)
            if self.verbose:
                self.print_log(f' - Updated {ticker} in {duration}s')

    def print_log(self, msg):
        print(f'{datetime.now()} {msg}', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Google Finance Prometheus Exporter')
    parser.add_argument('-f', '--config', help='Location of config yaml', required=True)
    parser.add_argument('-v', '--verbose', action='store_true', help='Print status to stdout')
    parser.add_argument('-p', '--port', help='Listening port (ip:port or just port)')
    parser.add_argument('-a', '--address', help='Listen address')
    parser.add_argument('-i', '--interval', help='Collection Interval')
    args = parser.parse_args()

    # Start up
    f = finance(args)
    if args.verbose:
        f.print_log(f'Running with config: ')
        f.print_config()
    f.start_server()

    while True:
        f.update()
        time.sleep(f.config['interval'])
