[![Python 3.11 | 3.12](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue)](https://www.python.org/downloads)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/Preocts/flask_playground/main.svg)](https://results.pre-commit.ci/latest/github/Preocts/flask_playground/main)
[![Python tests](https://github.com/Preocts/flask_playground/actions/workflows/python-tests.yml/badge.svg?branch=main)](https://github.com/Preocts/flask_playground/actions/workflows/python-tests.yml)

# flask_playground


Pizza datasource: [download](https://www.kaggle.com/datasets/mexwell/pizza-sales)


## Dev Setup

Assumes use of a virtual environment (venv)

### Install all dependencies and editable package

`python -m pip install -e .[dev,test]; pre-commit install`

### Build a database file

`python -m flask_playground.pizzastore`

### Set app secret key (optional)

`export FLASK_APP_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")`

A random key will be assigned to the app if not present in the environment
variables on launch. This will work in most cases but all sessions will be
invalidated on each launch.

### Launch test server

`python -m flask_playground.app`
