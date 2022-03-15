# datasette-hashed-urls

[![PyPI](https://img.shields.io/pypi/v/datasette-hashed-urls.svg)](https://pypi.org/project/datasette-hashed-urls/)
[![Changelog](https://img.shields.io/github/v/release/simonw/datasette-hashed-urls?include_prereleases&label=changelog)](https://github.com/simonw/datasette-hashed-urls/releases)
[![Tests](https://github.com/simonw/datasette-hashed-urls/workflows/Test/badge.svg)](https://github.com/simonw/datasette-hashed-urls/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/simonw/datasette-hashed-urls/blob/main/LICENSE)

Optimize Datasette performance behind a caching proxy

This plugin provides an alternative for Datasette's deprecated [Hashed URL mode](https://docs.datasette.io/en/0.60.2/performance.html#hashed-url-mode).

## Installation

Install this plugin in the same environment as Datasette.

    $ datasette install datasette-hashed-urls

## Usage

Once installed, this plugin will act on any immutable database files that are loaded into Datasette:

    datasette -i fixtures.db

The database will automatically be renamed to incorporate a hash of the contents of the SQLite file - so the above database would be served as:

    http://127.0.0.1:8001/fixtures_aa7318b

Every page that accesss that databasae, including JSON endpoints, will be served with a far-future cache expiry header.

A caching proxy such as Cloudflare can then be used to cache and accelerate content served by Datasette.

When the database file is updated and the server is restarted, the hash will change and content will be served from a new URL. Any hits to the previous hashed URLs will be automatically redirected.

## Development

To set up this plugin locally, first checkout the code. Then create a new virtual environment:

    cd datasette-hashed-urls
    python3 -mvenv venv
    source venv/bin/activate

Or if you are using `pipenv`:

    pipenv shell

Now install the dependencies and test dependencies:

    pip install -e '.[test]'

To run the tests:

    pytest
