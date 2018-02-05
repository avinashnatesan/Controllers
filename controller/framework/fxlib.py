# ipop-project
# Copyright 2016, University of Florida
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

ipop_ver_mjr = "18"
ipop_ver_mnr = "02"
ipop_ver_rev = "0"
ipop_ver_rel = "{0}.{1}.{2}".format(ipop_ver_mjr, ipop_ver_mnr, ipop_ver_rev)

# set default config values
MODULE_ORDER = ["CFx", "Logger", "OverlayVisualizer", "TincanInterface",
                "Signal", "LinkManager", "Topology", "Icc", "Broadcaster",
                "UsageReport"]
CONFIG = {
    "CFx": {
        "NodeId": "",  # Single unique node Id for all overlays
        "IpopVersion": ipop_ver_rel,
    },
    "Logger": {
        "Enabled": True,
        "LogLevel": "ERROR",      # Types of messages to log, <ERROR>/<WARNING>/<INFO>/<DEBUG>
        "Device": "File",      # Send logging output to <File> or <Console>
        "Directory": "./logs/",
        "CtrlLogFileName": "ctrl.log",
        "TincanLogFileName": "tincan.log",
        "MaxFileSize": 1000000,   # 1MB sized log files
        "MaxArchives": 5,   # Keep up to 5 files of history
        "ConsoleLevel": None
    },
    "OverlayVisualizer": {
        "Enabled": False,
        "TimerInterval": 30,                # Timer thread interval
        "WebServiceAddress": ":8080/IPOP",  # Visualizer webservice URL
        "NodeName": "",                     # Node Name as seen from the UI
        "Dependencies": ["Logger"]
    },
    "TincanInterface": {
        "Enabled": False,
        "MaxReadSize": 65507,               # Max buffer size for Tincan Messages
        "SocketReadWaitTime": 15,           # Socket read wait time for Tincan Messages
        "RcvServiceAddress": "127.0.0.1",   # Controller server address
        "SndServiceAddress": "127.0.0.1",   # Tincan server address
        "RcvServiceAddress6": "::1",
        "SndServiceAddress6": "::1",
        "CtrlRecvPort": 5801,               # Controller Listening Port
        "CtrlSendPort": 5800,               # Tincan Listening Port
        "Dependencies": ["Logger"]
    },
    "Signal": {
        "Enabled": False,
        "TimerInterval": 30,
        "MessagePerIntervalDelay": 10,      # No of XMPP messages after which the delay has to be increased
        "InitialAdvertismentDelay": 5,      # Initial delay for Peer XMPP messages
        "XmppAdvrtDelay": 5,                # Incremental delay for XMPP messages
        "MaxAdvertismentDelay": 60,         # Max XMPP Message delay
        "Dependencies": ["Logger"]
    },
    "LinkManager": {
        "Enabled": False,
        "TimerInterval": 30,                # Timer thread interval in sec
        "InitialLinkTTL": 120,              # Initial Time to Live for a p2p link in sec
        "LinkPulse": 180,                   # Time to Live for an online p2p link in sec
        "MaxConnRetry": 5,                  # Max Connection Retry attempts for each p2p link
        "Dependencies": ["Logger", "TincanInterface", "Signal"]
    },
    "Topology": {
        "Enabled": False,
        "TimerInterval": 30,
        "Dependencies": ["Logger", "TincanInterface", "LinkManager"]
    },
    "Icc": {
        "Enabled": False,
        "TimerInterval": 30,
        "Dependencies": ["Logger", "TincanInterface", "LinkManager"]
    },
    "Broadcaster": {
        "Enabled": False,
        "TimerInterval": 30,
        "Dependencies": ["Logger", "Topology", "Icc"]
    },
    "UsageReport": {
        "Enabled": False,
        "TimerInterval": 200,
        "ServerAddress": "metrics.ipop-project.org",
        "ServerPort": 8080,
        "Dependencies": ["Logger", "Signal"]
    }
}


def gen_ip6(uid, ip6=None):
    if ip6 is None:
        ip6 = CONFIG["TincanInterface"]["ip6_prefix"]
    for i in range(0, 16, 4):
        ip6 += ":" + uid[i:i + 4]
    return ip6
