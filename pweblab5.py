#!/usr/bin/env python

import socket
import ssl
from urllib.parse import urlparse, quote_plus
from bs4 import BeautifulSoup
import re
import argparse
import json
from datetime import datetime