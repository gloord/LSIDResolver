# LSID Resolver (client part)

### Description

Client part of a Life Science Identifer (LSID) resolver as a simple cli application for testing LSID resolving.
Authority and service wsdl files are stored in the cache folder (TTL = 2 days). Data and Metadata service responses 
are printed to the terminal.

For more information on LSIDs please visit [www.lsid.info](http://www.lsid.info/) 

## Requirements
- Python 3.x (tested with Python 3.7.2)
- See requirements.txt for package dependencies

## Installation
- Create a virtual environment and activate it 
(see [https://docs.python.org/3/library/venv.html](https://docs.python.org/3/library/venv.html))

- Install required packages
```
$ pip install -r requirements.txt
```

## Usage
```
$ python LSIDResolver.py -lsid urn:lsid:ipni.org:names:20012728-1
```

## Unit Tests
```
$ python -m unittest test.test_resolver -b
```

