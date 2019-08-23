#!/usr/local/bin/python3
import sys
import os
import socket
import time
import random
import string
import requests
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from statsd import StatsClient

def str2bool(val):
    if val and val.lower() != 'false':
        return bool(val)
    return False

REQUEST_URLS = os.getenv('REQUEST_URLS', None)
REQUEST_INTERNET = str2bool(os.getenv('REQUEST_INTERNET', False))
REQUEST_MALWARE = str2bool(os.getenv('REQUEST_MALWARE', False))
SEND_SQLI = str2bool(os.getenv('SEND_SQLI', False))
SEND_DIR_TRAVERSAL = str2bool(os.getenv('SEND_DIR_TRAVERSAL', False))
SEND_XSS = str2bool(os.getenv('SEND_XSS', False))
SEND_DGA = str2bool(os.getenv('SEND_DGA', False))
REQUEST_WAIT_SECONDS = float(os.getenv('REQUEST_WAIT_SECONDS', 3.0))
REQUEST_BYTES = int(os.getenv('REQUEST_BYTES', 1024))
STOP_SECONDS = int(os.getenv('STOP_SECONDS', 0))
STOP_PADDING = str2bool(os.getenv('STOP_PADDING', False))
ATTACK_PROBABILITY = float(os.getenv('ATTACK_PROBABILITY', 0.01))
EGRESS_PROBABILITY = float(os.getenv('EGRESS_PROBABILITY', 0.1))
STATS_PORT = os.getenv('STATS_PORT', None)
STATSD_HOST = os.getenv('STATSD_HOST', None)
STATSD_PORT = int(os.getenv('STATSD_PORT', 8125))
START_TIME = int(time.time())
HOST_NAME = ''

padding = 0
if STOP_PADDING:
    padding = random.choice(range(STOP_SECONDS))

stats = {
    'Total': {
        'Requests': 0,
        'Sent Bytes': 0,
        'Received Bytes': 0,
        'Internet Requests': 0,
        'Attacks': 0,
        'SQLi': 0,
        'XSS': 0,
        'Directory Traversal': 0,
        'DGA': 0,
        'Malware': 0,
        'Error': 0
    },
    'Last 30 Seconds': {
        'Requests': 0,
        'Sent Bytes': 0,
        'Received Bytes': 0,
        'Internet Requests': 0,
        'Attacks': 0,
        'SQLi': 0,
        'XSS': 0,
        'Directory Traversal': 0,
        'DGA': 0,
        'Malware': 0,
        'Error': 0
    }
}

if STATSD_HOST:
    client_stats = StatsClient(prefix='all_clients',
                               host=STATSD_HOST,
                               port=STATSD_PORT)

    host_stats = StatsClient(prefix='client-' + socket.gethostname(),
                             host=STATSD_HOST,
                             port=STATSD_PORT)

class httpd(BaseHTTPRequestHandler):
    server_name = socket.gethostname()
    server_ip = socket.gethostbyname(server_name)

    def do_GET(self):
        """json api response"""
        host_header = self.headers['Host']
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.response = {
            'time': time.asctime(),
            'runtime': int(time.time() - START_TIME),
            'hostname': self.server_name,
            'ip': self.server_ip,
            'stats': stats['Total'],
            'config': {
                'STATS_PORT': int(STATS_PORT),
                'STATSD_HOST': STATSD_HOST,
                'STATSD_PORT': STATSD_PORT,
                'REQUEST_URLS': REQUEST_URLS,
                'REQUEST_INTERNET': REQUEST_INTERNET,
                'REQUEST_MALWARE': REQUEST_MALWARE,
                'SEND_SQLI': SEND_SQLI,
                'SEND_DIR_TRAVERSAL': SEND_DIR_TRAVERSAL,
                'SEND_XSS': SEND_XSS,
                'SEND_DGA': SEND_DGA,
                'REQUEST_WAIT_SECONDS': REQUEST_WAIT_SECONDS,
                'REQUEST_BYTES': REQUEST_BYTES,
                'STOP_SECONDS': STOP_SECONDS,
                'ATTACK_PROBABILITY': ATTACK_PROBABILITY,
                'EGRESS_PROBABILITY': EGRESS_PROBABILITY
            }
        }
        body = json.dumps(self.response, indent=2)
        self.wfile.write(body.encode('utf-8'))

class state():
    last_timestamp = START_TIME

def every_30_seconds():
    if state.last_timestamp + 30 > int(time.time()):
        return False

    state.last_timestamp = int(time.time())
    return True

def keep_running():
    if not REQUEST_URLS:
        sys.exit('Server killed - REQUEST_URLS environment variable required.')

    if (STOP_SECONDS != 0) and ((START_TIME + STOP_SECONDS + padding) < int(time.time())):
        sys.exit('Server killed after ' + str(int(STOP_SECONDS) + int(padding)) + ' seconds.')

    return True

def insert_data():
    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(REQUEST_BYTES)])

def statistics_server():
    if STATS_PORT:
        stats_server = HTTPServer((HOST_NAME, int(STATS_PORT)), httpd)
        stats_server.serve_forever()

def main():
    while keep_running():
        if every_30_seconds():
            # Print and clear statistics
            print(json.dumps(stats))
            stats['Last 30 Seconds'] = {
                'Requests': 0,
                'Sent Bytes': 0,
                'Received Bytes': 0,
                'Internet Requests': 0,
                'Attacks': 0,
                'SQLi': 0,
                'XSS': 0,
                'Directory Traversal': 0,
                'DGA': 0,
                'Malware': 0,
                'Error': 0
            }

        url_list = REQUEST_URLS.split(',')

        json_body = {'data': insert_data()}

        for url in url_list:
            try:
                response = requests.post(url, json=json_body)
                print('Request to ' + response.url + '   Request size: ' + str(len(response.request.body)) + '   Response size: ' + str(len(response.content)))
                stats['Total']['Requests'] += 1
                stats['Last 30 Seconds']['Requests'] += 1
                stats['Total']['Sent Bytes'] += len(response.request.body)
                stats['Last 30 Seconds']['Sent Bytes'] += len(response.request.body)
                stats['Total']['Received Bytes'] += len(response.content)
                stats['Last 30 Seconds']['Received Bytes'] += len(response.content)

                if STATSD_HOST:
                    client_stats.incr('requests')
                    client_stats.incr('sent_bytes', len(response.request.body))
                    client_stats.incr('received_bytes', len(response.content))
                    host_stats.incr('requests')
                    host_stats.incr('sent_bytes', len(response.request.body))
                    host_stats.incr('received_bytes', len(response.content))

            except Exception as e:
                print(str(e) + ' error to: ' + url)
                stats['Total']['Error'] += 1
                stats['Last 30 Seconds']['Error'] += 1

                if STATSD_HOST:
                    client_stats.incr('error')
                    host_stats.incr('error')

            if SEND_SQLI:
                if random.random() < ATTACK_PROBABILITY:
                    parameters = {
                        'username': 'joe@example.com',
                        'password': ';UNION SELECT 1, version() limit 1,1--'
                    }

                    try:
                        sqli = requests.get(url, params=parameters)
                        print('SQLi sent: ' + sqli.url)
                        stats['Total']['SQLi'] += 1
                        stats['Last 30 Seconds']['SQLi'] += 1
                        stats['Total']['Attacks'] += 1
                        stats['Last 30 Seconds']['Attacks'] += 1

                        if STATSD_HOST:
                            client_stats.incr('sqli')
                            client_stats.incr('attacks')
                            host_stats.incr('sqli')
                            host_stats.incr('attacks')

                    except Exception as e:
                        print(str(e) + ' error to: ' + url)
                        stats['Total']['Error'] += 1
                        stats['Last 30 Seconds']['Error'] += 1

                        if STATSD_HOST:
                            client_stats.incr('error')
                            host_stats.incr('error')

            if SEND_XSS:
                if random.random() < ATTACK_PROBABILITY:
                    parameters = {
                        'username': 'joe@example.com',
                        'password': "pwd<script>alert('attacked')</script>"
                    }

                    try:
                        xss = requests.get(url, params=parameters)
                        print('XSS sent: ' + xss.url)
                        stats['Total']['XSS'] += 1
                        stats['Last 30 Seconds']['XSS'] += 1
                        stats['Total']['Attacks'] += 1
                        stats['Last 30 Seconds']['Attacks'] += 1

                        if STATSD_HOST:
                            client_stats.incr('xss')
                            client_stats.incr('attacks')
                            host_stats.incr('xss')
                            host_stats.incr('attacks')

                    except Exception as e:
                        print(str(e) + ' error to: ' + url)
                        stats['Total']['Error'] += 1
                        stats['Last 30 Seconds']['Error'] += 1

                        if STATSD_HOST:
                            client_stats.incr('error')
                            host_stats.incr('error')

            if SEND_DIR_TRAVERSAL:
                if random.random() < ATTACK_PROBABILITY:
                    parameters = {
                        'username': 'joe@example.com',
                        'password': '../../../../../passwd'
                    }

                    try:
                        dirtraversal = requests.get(url, params=parameters)
                        print('Directory Traversal sent: ' + dirtraversal.url)
                        stats['Total']['Directory Traversal'] += 1
                        stats['Last 30 Seconds']['Directory Traversal'] += 1
                        stats['Total']['Attacks'] += 1
                        stats['Last 30 Seconds']['Attacks'] += 1

                        if STATSD_HOST:
                            client_stats.incr('directory_traversal')
                            client_stats.incr('attacks')
                            host_stats.incr('directory_traversal')
                            host_stats.incr('attacks')

                    except Exception as e:
                        print(str(e) + ' error to: ' + url)
                        stats['Total']['Error'] += 1
                        stats['Last 30 Seconds']['Error'] += 1

                        if STATSD_HOST:
                            client_stats.incr('error')
                            host_stats.incr('error')

        if REQUEST_INTERNET:
            if random.random() < EGRESS_PROBABILITY:
                egress_sites = [
                    'http://mirror.facebook.net/centos/',
                    'http://mirror.rackspace.com/CentOS/',
                    'http://mirrors.edge.kernel.org/centos/',
                    'http://mirrors.oit.uci.edu/centos/',
                    'http://www.gtlib.gatech.edu/pub/centos/',
                    'http://mirror.grid.uchicago.edu/pub/linux/centos/',
                    'http://mirror.cc.columbia.edu/pub/linux/centos/',
                    'http://yum.tamu.edu/centos/',
                    'http://mirror.cogentco.com/pub/linux/centos/',
                    'http://mirror.cs.vt.edu/pub/CentOS/',
                    'http://centos.s.uw.edu/centos/'
                ]

                egress_site = random.choice(egress_sites)
                egress_internet = requests.Session()
                
                try:
                    egress_internet = egress_internet.get(egress_site, allow_redirects=True)
                    print('Internet request to: ' + egress_internet.url)
                    stats['Total']['Internet Requests'] += 1
                    stats['Last 30 Seconds']['Internet Requests'] += 1
                    stats['Total']['Received Bytes'] += len(egress_internet.content)
                    stats['Last 30 Seconds']['Received Bytes'] += len(egress_internet.content)

                    if STATSD_HOST:
                        client_stats.incr('internet_requests')
                        client_stats.incr('received_bytes', len(egress_internet.content))
                        host_stats.incr('internet_requests')
                        host_stats.incr('received_bytes', len(egress_internet.content))

                except Exception as e:
                    print(str(e) + ' error to: ' + url)
                    stats['Total']['Error'] += 1
                    stats['Last 30 Seconds']['Error'] += 1

                    if STATSD_HOST:
                        client_stats.incr('error')
                        host_stats.incr('error')

        if REQUEST_MALWARE:
            if random.random() < ATTACK_PROBABILITY:
                eicar = requests.Session()
                
                try:
                    eicar = eicar.get('http://www.eicar.org/download/eicar.com.txt')
                    print('Malware downloaded: ' + eicar.text)
                    stats['Total']['Malware'] += 1
                    stats['Last 30 Seconds']['Malware'] += 1
                    stats['Total']['Attacks'] += 1
                    stats['Last 30 Seconds']['Attacks'] += 1

                    if STATSD_HOST:
                        client_stats.incr('malware')
                        client_stats.incr('attacks')
                        host_stats.incr('malware')
                        host_stats.incr('attacks')

                except Exception as e:
                    print(str(e) + ' error to: ' + url)
                    stats['Total']['Error'] += 1
                    stats['Last 30 Seconds']['Error'] += 1

                    if STATSD_HOST:
                        client_stats.incr('error')
                        host_stats.incr('error')

        if SEND_DGA:
            if random.random() < ATTACK_PROBABILITY:
                dga_domains = [
                    't3622c4773260c097e2e9b26705212ab85.ws',
                    'u83ccf36d9f02e9ea79a9d16c0336677e4.to',
                    'v02bec0c090508bc76b3ea81dfc2198a71.in',
                    'wa9e4628c334324e181e40f33f878c153f.hk',
                    'xdcc5481252db5f38d5fc18c9ad3b2f7fd.cn',
                    'yf32d9ac7f0a9f463e8da4736b12d7044a.tk'
                ]

                dga = random.choice(dga_domains)

                try:
                    dga_response = socket.gethostbyname(dga)
                    print('DGA query sent: ' + dga + '   Response: ' + dga_response)
                    stats['Total']['DGA'] += 1
                    stats['Last 30 Seconds']['DGA'] += 1
                    stats['Total']['Attacks'] += 1
                    stats['Last 30 Seconds']['Attacks'] += 1
                    
                    if STATSD_HOST:
                        client_stats.incr('dga')
                        client_stats.incr('attacks')
                        host_stats.incr('dga')
                        host_stats.incr('attacks')

                except Exception as e:
                    print(str(e) + ' error resolving: ' + dga)
                    stats['Total']['Error'] += 1
                    stats['Last 30 Seconds']['Error'] += 1

                    if STATSD_HOST:
                        client_stats.incr('error')
                        host_stats.incr('error')

        time.sleep(REQUEST_WAIT_SECONDS)

stats_thread = threading.Thread(target=statistics_server, daemon=True)
stats_thread.start()

main()
