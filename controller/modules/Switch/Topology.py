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

from controller.framework.ControllerModule import ControllerModule
from controller.framework.CFx import CFX
try:
    import simplejson as json
except ImportError:
    import json
from collections import defaultdict

class Topology(ControllerModule, CFX):
    def __init__(self, cfx_handle, module_config, module_name):
        super(Topology, self).__init__(cfx_handle, module_config, module_name)
        self._overlays = {}

    def initialize(self):
        self._cfx_handle.start_subscription("Signal",
                                            "SIG_PEER_PRESENCE_NOTIFY")
        self._cfx_handle.start_subscription("TincanInterface",
                                            "TCI_TINCAN_MSG_NOTIFY")
        self._cfx_handle.start_subscription("LinkManager",
                                                "LNK_DATA_UPDATES")

        overlay_ids = self._cfx_handle.query_param("Overlays")
        self._links = dict()
        for olid in overlay_ids:
            self._overlays[olid] = (
                dict(Descriptor=dict(IsReady=False, State="Bootstrapping"),
                     Peers=dict(), Links=dict()))
            """
            Peers is dictionary indexed by peer id and maps to state
            of peer, ex: Peers= {peer_id="peer_state"}
            """
            #if self._cm_config["Overlays"][olid]["Type"] == "VNET":
            #    self.create_overlay(self._cm_config["Overlays"][olid], olid)
        try:
            # Subscribe for data request notifications from OverlayVisualizer
            self._cfx_handle.start_subscription("OverlayVisualizer",
                                                "VIS_DATA_REQ")
        except NameError as err:
            if "OverlayVisualizer" in str(err):
                self.register_cbt("Logger", "LOG_WARNING",
                                  "OverlayVisualizer module not loaded."
                                  " Visualization data will not be sent.")
        self.register_cbt("Logger", "LOG_INFO", "Module loaded")

    def terminate(self):
        pass

    #def create_overlay(self, overlay_cfg, overlay_id):
    #    param = {
    #        "StunAddress": self._cm_config["Stun"][0],
    #        "TurnAddress": self._cm_config["Turn"][0]["Address"],
    #        "TurnPass": self._cm_config["Turn"][0]["Password"],
    #        "TurnUser": self._cm_config["Turn"][0]["User"],
    #        "Type": overlay_cfg["Type"],
    #        "EnableIPMapping": overlay_cfg.get("EnableIPMapping", False),
    #        "TapName": overlay_cfg["TapName"],
    #        "IP4": overlay_cfg["IP4"],
    #        "MTU4": overlay_cfg["MTU4"],
    #        "PrefixLen4": overlay_cfg["IP4PrefixLen"],
    #        "OverlayId": overlay_id
    #    }
    #    self.register_cbt("TincanInterface", "TCI_CREATE_OVERLAY", param)

    def connect_to_peer(self, overlay_id, peer_id):
        # only send the create link request is we have overlay info from tincan
        # this is where we get the local fingerprint/mac and more which necessary
        # for creating the link
        self.register_cbt("Logger", "LOG_DEBUG", "Connecting to peer "
            "{0}:{1}->{2}".format(overlay_id, self._cm_config["NodeId"], peer_id))
        if (self._overlays[overlay_id]["Peers"]
                .get(peer_id, "PeerStateUnknown") != "PeerStateConnected"
                and self._cm_config["NodeId"] < peer_id):
            params = {
                "OverlayId": overlay_id,
                "PeerId": peer_id,
                "EncryptionEnabled":
                self._cm_config["Overlays"][overlay_id]["EncryptionEnabled"]}
            #    ,
            #    "EncryptionEnabled": self._cm_config["Overlays"][overlay_id].get("EncryptionEnabled", True),
            #    "NodeData": self._overlays[overlay_id]["Descriptor"]
            #    "StunAddress": self._cm_config["Stun"][0],
            #    "TurnAddress": self._cm_config["Turn"][0]["Address"],
            #    "TurnPass": self._cm_config["Turn"][0]["Password"],
            #    "TurnUser": self._cm_config["Turn"][0]["User"],
            #    "Type": overlay_cfg["Type"],
            #    "EnableIPMapping": overlay_cfg.get("EnableIPMapping", False),
            #    "TapName": overlay_cfg["TapName"],
            #    "IP4": overlay_cfg["IP4"],
            #    "MTU4": overlay_cfg["MTU4"],
            #    "PrefixLen4": overlay_cfg["IP4PrefixLen"],
            #}
            #params["NodeData"]["UID"] = self._cm_config["NodeId"]
            self.register_cbt("LinkManager", "LNK_CREATE_LINK", params)

    def resp_handler_create_link(self, cbt):
        olid = cbt.request.params["OverlayId"]
        peer_id = cbt.request.params["PeerId"]
        if cbt.response.status:
            self._overlays[olid]["Peers"][peer_id] = "PeerStateConnected"
        else:
            self._overlays[olid]["Peers"].pop(peer_id, None)
            self.register_cbt("Logger", "LOG_WARNING",
                              "Link Creation Failed {0}".format(cbt.response.data))

    def resp_handler_query_overlay_info(self, cbt):
        if cbt.response.status:
            olid = cbt.request.params["OverlayId"]
            self._overlays[olid]["Descriptor"]["IsReady"] = cbt.response.status
            cbt_data = json.loads(cbt.response.data)
            self._overlays[olid]["Descriptor"]["MAC"] = cbt_data["MAC"]
            self._overlays[olid]["Descriptor"]["PrefixLen"] = cbt_data["IP4PrefixLen"]
            self._overlays[olid]["Descriptor"]["VIP4"] = cbt_data["VIP4"]
            self._overlays[olid]["Descriptor"]["TapName"] = cbt_data["TapName"]
            self._overlays[olid]["Descriptor"]["FPR"] = cbt_data["FPR"]
        else:
            self.register_cbt("Logger", "LOG_WARNING",
                              "Query overlay info failed {0}".format(cbt.response.data))
            # retry the query
            self.register_cbt("TincanInterface", "TCI_QUERY_OVERLAY_INFO", cbt.request.params)

    #def resp_handler_create_overlay(self, cbt):
    #    if cbt.response.status:
    #        self.register_cbt("TincanInterface", "TCI_QUERY_OVERLAY_INFO", {
    #                          "OverlayId": cbt.request.params["OverlayId"]})
    #    else:
    #        self.register_cbt("Logger", "LOG_WARNING", cbt.response.data)
    #        # retry creating the overlay once
    #        if self._overlays[cbt.request.params["OverlayId"]].get("RetryCount", 0) < 1:
    #            self._overlays[cbt.request.params["OverlayId"]]["RetryCount"] = 1
    #            self.register_cbt("TincanInterface", "TCI_CREATE_OVERLAY", cbt.request.params)

    def req_handler_peer_presence(self, cbt):
        peer = cbt.request.params
        self._overlays[peer["OverlayId"]]["Peers"][peer["PeerId"]] = "PeerStateAvailable"
        self._overlays[peer["OverlayId"]]["Descriptor"]["State"] = "Isolated"
        self.connect_to_peer(peer["OverlayId"], peer["PeerId"])
        cbt.set_response(None, True)
        self.complete_cbt(cbt)

    def req_handler_query_peer_ids(self, cbt):
        peer_ids = {}
        try:
            for olid in self._cm_config["Overlays"]:
                peer_ids[olid] = set(self._overlays[olid]["Peers"].keys())
            cbt.set_response(data=peer_ids, status=True)
            self.complete_cbt(cbt)
        except KeyError:
            cbt.set_response(data=None, status=False)
            self.complete_cbt(cbt)
            self.register_cbt("Logger", "LOG_WARNING", "Overlay Id is not valid {0}".format(cbt.response.data))

    def vis_data_response(self, cbt):
        topo_data = defaultdict(dict)
        try:
            for olid in self._cm_config["Overlays"]:
                #if self._overlays[olid]["Descriptor"]["IsReady"]:
                    topo_data[olid]["TapName"] = self._overlays[olid]["Descriptor"]["TapName"]
                    # self._overlays[olid]["Descriptor"]["GeoIP"] # TODO: GeoIP
                    topo_data[olid]["GeoIP"] = "128.277.9.98"
                    topo_data[olid]["VIP4"] = self._overlays[olid]["Descriptor"]["VIP4"]
                    topo_data[olid]["PrefixLen"] = self._overlays[olid]["Descriptor"]["PrefixLen"]
                    topo_data[olid]["MAC"] = self._overlays[olid]["Descriptor"]["MAC"]
            if len(topo_data) == 0:
                topo_data = None
                status = False
            else:
                status = True
            cbt.set_response({"Topology": topo_data}, status)
            self.complete_cbt(cbt)
        except KeyError:
            cbt.set_response(data=None, status=False)
            self.complete_cbt(cbt)
            self.register_cbt("Logger", "LOG_WARNING", "Topology data not available {0}".format(cbt.response.data))

    def _broadcast_frame(self, cbt):
        if cbt.request.params["Command"] == "ReqRouteUpdate":
            eth_frame = cbt.request.params["Data"]
            tgt_mac_id = eth_frame[:12]
            if tgt_mac_id == "FFFFFFFFFFFF":
                arp_broadcast_req = {
                    "overlay_id": cbt.request.params["OverlayId"],
                    "tgt_module": "TincanInterface",
                    "action": "TCI_INJECT_FRAME",
                    "payload": eth_frame
                }
                self.register_cbt("Broadcaster", "BDC_BROADCAST",
                                  arp_broadcast_req)
            cbt.set_response(data=None, status=True)
        else:
            cbt.set_response(data=None, status=False)

        self.complete_cbt(cbt)
    
    def link_data_update_handler(self, cbt):
        params = cbt.request.params
        olid = params["OverlayId"]
        linkid = params["LinkId"]
        if params["UpdateType"] == "ADDED":
            self._links[linkid] = params["PeerId"]
        elif params["UpdateType"] == "REMOVED":
            peer = self._links.pop(linkid, None)
            self._overlays[olid]["Peers"].pop(peer)
        cbt.set_response(None, True)
        self.complete_cbt(cbt)

    def process_cbt(self, cbt):
        if cbt.op_type == "Request":
            if cbt.request.action == "SIG_PEER_PRESENCE_NOTIFY":
                self.req_handler_peer_presence(cbt)
            elif cbt.request.action == "VIS_DATA_REQ":
                self.vis_data_response(cbt)
            elif cbt.request.action == "TOP_QUERY_PEER_IDS":
                self.req_handler_query_peer_ids(cbt)
            elif cbt.request.action == "TCI_TINCAN_MSG_NOTIFY":
                self._broadcast_frame(cbt)
            elif cbt.request.action == "LNK_DATA_UPDATES":
                self.link_data_update_handler(cbt)
        elif cbt.op_type == "Response":
            #if cbt.request.action == "TCI_CREATE_OVERLAY":
            #    self.resp_handler_create_overlay(cbt)
            if cbt.request.action == "TCI_QUERY_OVERLAY_INFO":
                self.resp_handler_query_overlay_info(cbt)
            elif cbt.request.action == "LNK_CREATE_LINK":
                self.resp_handler_create_link(cbt)
            elif cbt.request.action == "BDC_BROADCAST":
                if not cbt.response.status:
                    self.register_cbt(
                        "Logger", "LOG_WARNING",
                        "Broadcast failed. Data: {0}".format(
                            cbt.response.data))

            self.free_cbt(cbt)

    def timer_method(self):
        try:
            #self.register_cbt("LinkManger","LNK_QUERY_LINKS")
            #for overlay_id in self._overlays:
            #    for peer_id in self._overlays[overlay_id]["Peers"]:
            #        self.connect_to_peer(overlay_id, peer_id)
            pass
        except Exception as err:
            self.register_cbt("Logger", "LOG_ERROR", "Exception in BTM timer:" + str(err))