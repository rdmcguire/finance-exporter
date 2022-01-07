# finance-exporter
**Prometheus Exporter for Market Data**
This exporter allows you to define metrics and labels to be collected
and served on a prometheus metrics endpoint.

Currently, three APIs are supported:
  * Yahoo Finance
	* IEXCloud
	* AlphaVantage

For IEXCloud and AlphaVantage, an API key must be specified in api_key for the source.

## Configuration
Configuration is well defined in schema.yaml. The primary sections are:
  1. Global parameters
	1. Tickers
	1. Sources

For each source, metrics and labels are defined. If using multiple sources,
the metrics will be build with the full combination of labels. This is to allow
for a more rich source of data to populate metrics for less rich, data-only type
APIs. For instance, Yahoo Finance provides many details in their quote that IEXCloud
lacks, but IEXCloud has metrics that Yahoo Finance lacks. You can define the labels
on Yahoo Finance and they will be added to metrics of the same symbol from IEXCloud.

If you have more than one source and the full set of labels are not collected
from both, be certain to set `update_cache_on_startup: true`

**Global Settings**
```yaml`
port: 8000
address: 0.0.0.0
metric_prefix: finance
min_interval: 15
update_cache_on_startup: false
```
**Tickers**
```yaml
tickers:
  - AAPL
  - GOOG
	```
**Sources**
```yaml
sources:
  - name: yahoo
    interval: 300
    plugin: yfinance
    metrics:
```
**Metrics**
```yaml
      open_price:
        item: regularMarketOpen
        type: Gauge
        help: Day Open Price
      previous_close:
        item: regularMarketPreviousClose
        type: Gauge
        help: Previous Closing Price
```
**Labels**
```yaml
    labels:
      ticker: symbol
      type: quoteType
      name: shortName
      exchange: exchange
      recommendation: recommendationKey
      sector: sector
			```

## Running the exporter
If you want to run as-is, simply install modules in requirements.txt
using your preferred means (e.g. pip3 install -r requirements.txt) and run.

**Script Options**
```bash
usage: finance-exporter.py [-h] -f CONFIG [-v] [-p PORT] [-a ADDRESS] [-d]

Google Finance Prometheus Exporter

optional arguments:
  -h, --help            show this help message and exit
  -f CONFIG, --config CONFIG
                        Location of config yaml
  -v, --verbose         Print status to stdout
  -p PORT, --port PORT  Listening port (ip:port or just port)
  -a ADDRESS, --address ADDRESS
                        Listen address
  -d, --debug           Dump API Data
  ```
### Running in Docker
A docker-compose is provided showing the location of the config volume as well as env vars.

You can run directly via docker / podman, or you can run with docker-compose. There is nothing
particularly special to add, and since this isn't docker training, this is an execise for the
reader.

I'm not currently publishing this to dockerhub or anywhere else, since I'm currently the only
user of it in the world that I'm aware of. Do prove me wrong!
