#!/usr/bin/python3
import argparse
import time
from datetime import datetime
import yaml
import yfinance as yf
from prometheus_client import start_http_server, Counter, Gauge, Summary, Histogram
from includes.alphavantage import AlphaVantage
import iexfinance.stocks as iex
# Debug
from pprint import pprint

class finance:

    def __init__(self, args):
        # Prepare the config
        self.config = dict()
        # This is hard-coded, see finance.update() quote_info declaration
        self.default_labels     = list(['plugin', 'source', 'ticker'])
        self.load_config(args.config)
        # Set up -- prefer command line arg to yaml arg
        self.verbose            = args.verbose
        self.debug              = args.debug
        self.config['port']     = next(v for v in [ args.port, self.config.get('port') ] if v is not None)
        self.config['address']  = next(v for v in [ args.address, self.config.get('address') ] if v is not None)
        # Ensure we have sources
        if self.config.get('sources') is None:
            raise Exception('Refusing to initialize with no defined sources')
        # Setup plugins
        self.sources            = self.load_sources()
        # Prep unique list of labels and metrics
        self.labels             = self.load_labels()
        self.metrics            = self.load_metrics()
        # Prepare label cache
        self.label_cache        = dict()
        for ticker in self.config['tickers']:
            self.label_cache[ticker] = { label: None for label in self.labels }
        # Prometheus Metrics
        self.prom_metrics               = dict()
        if self.verbose:
            self.print_log(f'Preparing default metrics with labels: {self.labels}')
        self.prom_metrics['updates']    = Counter(f"{self.config['metric_prefix']}_updates", 'Number of ticker updates', self.labels)
        self.prom_metrics['quote_time'] = Gauge(f"{self.config['metric_prefix']}_quote_time", 'Time spent retrieving quote', self.labels)
        # Initialized Configured Metrics
        self.init_metrics()

    def load_config(self, config_file):
        with open(config_file, 'r') as config_file:
            self.config = yaml.load(config_file, Loader=yaml.FullLoader)

    def print_config(self):
        self.print_log(pprint(self.config))

    def load_sources(self):
        sources = dict()
        for source in self.config['sources']:
            sources[source['name']] = source
            if source['plugin'] == 'alphavantage':
                if source.get('api_key') is None:
                    raise Exception(f"Source {source['name']} must provide API Key for AlphaVantage to use plugin")
                sources[source['name']]['handler'] = AlphaVantage(source['api_key'])
            elif source['plugin'] == 'iexcloud':
                if source.get('api_key') is None:
                    raise Exception(f"Source {source['name']} must provide API Key for IEXCloud to use plugin")
                sources[source['name']]['handler'] = iex
            elif source['plugin'] == 'yfinance':
                sources[source['name']]['handler'] = yf
        return sources

    def load_labels(self):
        labels = self.default_labels.copy()
        for source in self.config['sources']:
            if source.get('labels') is not None:
                labels = list(set(labels + list(source['labels'].keys())))
        return labels

    def load_metrics(self):
        metrics = dict()
        for source in self.config['sources']:
            # Define source for metric in-case of overlap
            for metric in source['metrics'].keys():
                source['metrics'][metric].update({ 'source': source['name'] })
            metrics.update(source['metrics'])
        return metrics

    def init_metrics(self):
        for name, metric in self.metrics.items():
            if self.verbose:
                self.print_log(f"Preparing metric {name}({metric['type']}) from {metric['source']}")
            if metric['type'] == 'Counter':
                self.prom_metrics[name] = Counter(f"{self.config['metric_prefix']}_{name}", metric['help'], self.labels)
            elif metric['type'] == 'Gauge':
                self.prom_metrics[name] = Gauge(f"{self.config['metric_prefix']}_{name}", metric['help'], self.labels)
            elif metric['type'] == 'Histogram':
                self.prom_metrics[name] = Histogram(f"{self.config['metric_prefix']}_{name}", metric['help'], self.labels)
            elif metric['type'] == 'Summary':
                self.prom_metrics[name] = Summary(f"{self.config['metric_prefix']}_{name}", metric['help'], self.labels)

    def start_server(self):
        if self.verbose:
            self.print_log(f"Starting HTTP Server on {self.config['address']}:{self.config['port']}")
        start_http_server(int(self.config['port']), addr=self.config['address'])

    def fetch_data(self, source, ticker):
        handler = source['handler']
        if source['plugin'] == 'yfinance':
            return handler.Ticker(ticker).info
        elif source['plugin'] == 'alphavantage':
            handler.ticker(ticker)
            return handler.get_all()
        elif source['plugin'] == 'iexcloud':
            stock = handler.Stock(ticker, output_format='json',token = source['api_key']).get_quote()
            return stock

    def update(self, source):
        for ticker in self.config['tickers']:
            if self.verbose:
                self.print_log(f"Updating ticker {ticker} from {source['name']}")
            start_time = time.time()
            quote = dict()
            try:
                quote = self.fetch_data(source, ticker)
                if self.debug:
                    pprint(quote)
            except Exception as e:
                print(f'Error fetching {ticker}: {e}')
                continue
            duration = time.time() - start_time
            # Update label values from Quote
            quote_info = dict({
                'source': source['name'],
                'plugin': source['plugin'],
                'ticker': ticker,
            })
            if source.get('labels') is not None:
                quote_info.update({ label: quote.get(field) for label, field in source.get('labels').items() if quote.get(field) is not None })
            # Update Cache
            self.label_cache[ticker].update(quote_info)
            # Fill in the blanks
            quote_info.update({ label: self.label_cache[ticker][label] for label in self.labels if quote_info.get(label) is None })
            # Update Metrics
            if self.debug:
                self.print_log(f'Preparing to load metrics with labels: {quote_info}')
            self.prom_metrics['updates'].labels(**quote_info).inc()
            self.prom_metrics['quote_time'].labels(**quote_info).set(duration)
            # Update Configured Metrics
            for name, metric in self.metrics.items():
                if metric['source'] != source['name']:
                    continue
                value = quote.get(metric['item'])
                if value is None:
                    continue
                if metric['type'] == 'Counter':
                    self.prom_metrics[name].labels(**quote_info).inc()
                elif metric['type'] == 'Gauge':
                    self.prom_metrics[name].labels(**quote_info).set(value)
                elif metric['type'] == 'Histogram':
                    self.prom_metrics[name].labels(**quote_info).observe(value)
                elif metric['type'] == 'Summary':
                    self.prom_metrics[name].labels(**quote_info).observe(value)
            if self.verbose:
                self.print_log(f" - Updated {ticker} from {source['name']} in {duration}s")

    def print_log(self, msg):
        print(f'{datetime.now()} {msg}', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Google Finance Prometheus Exporter')
    parser.add_argument('-f', '--config', help='Location of config yaml', required=True)
    parser.add_argument('-v', '--verbose', action='store_true', help='Print status to stdout')
    parser.add_argument('-p', '--port', help='Listening port (ip:port or just port)')
    parser.add_argument('-a', '--address', help='Listen address')
    parser.add_argument('-d', '--debug', action="store_true",help="Dump API Data")
    args = parser.parse_args()

    # Start up
    f = finance(args)
    if args.debug:
        f.print_log(f'Running with config: ')
        f.print_config()
    f.start_server()

    # Track Updates
    last_run = dict()
    for name, source in f.sources.items():
        last_run[name] = 0

    # Update in loop
    while True:
        for name, source in f.sources.items():
            if time.time() - last_run[name] > source['interval']:
                if args.verbose:
                    f.print_log(f"Updating Source {name}")
                f.update(source)
                last_run[name] = time.time()
        time.sleep(f.config['min_interval'])
