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

import time
import threading
import uuid
import copy
try:
    import simplejson as json
except ImportError:
    import json
from controller.framework.ControllerModule import ControllerModule


class LinkManager(ControllerModule):

    def __init__(self, cfx_handle, module_config, module_name):
        super(LinkManager, self).__init__(cfx_handle, module_config, module_name)
        self.maxretries = self._cm_config["MaxConnRetry"]
        self._peers = {}
        self._overlays = {}  # indexed by overlay ID, taaged with an overlay ID
        self._links = {}  # indexed by link id, which is unique
        self._lock = threading.Lock() # serializes access to _overlays,_links

    def initialize(self):
        self._link_updates_publisher = \
                self._cfx_handle.publish_subscription("LNK_DATA_UPDATES")
        try:
            # Subscribe for data request notifications from OverlayVisualizer
            self._cfx_handle.start_subscription("OverlayVisualizer",
                                                "VIS_DATA_REQ")
        except NameError as e:
            if "OverlayVisualizer" in str(e):
                self.register_cbt("Logger", "LOG_WARNING",
                                  "OverlayVisualizer module not loaded."
                                  " Visualization data will not be sent.")
        self.register_cbt("Logger", "LOG_INFO", "Module Loaded")

    def req_link_endpt_from_peer(self, cbt):
        """
        The caller provides the overlay id which contains the link and the peer id
        which the link connects. The link id is generated here and returned to the
        caller. This is done only after the local enpoint is created, but can
        occur before the link is ready. The link status can be queried to determine
        when it is writeable.
        We request creatation of the remote endpoint first to avoid cleaning up a
        local endpoint if the peer denies our request. The link id is communicated
        in the request and will be the same at both nodes.
        """
        olid = cbt.request.params["OverlayId"]
        peerid = cbt.request.params["PeerId"]
        self._lock.acquire()
        if self._overlays.get(olid) is None:
            self._overlays[olid] = dict(Peers=dict())
        if peerid in self._overlays[olid]["Peers"]:
            # Link already exists ask TM to clean up first
            self._lock.release()
            cbt.set_response("LINK EXISTS", False)
            self.complete_cbt(cbt)
            return
        else:
            lnkid = uuid.uuid4().hex
            self._overlays[olid]["Peers"][peerid] = lnkid  # index for quick peer->link lookup
            self._links[lnkid] = dict(Stats=dict())
            self._lock.release()

        msg = {
            "OverlayId": olid,
            "LinkId": lnkid,
            "EncryptionEnabled": cbt.request.params["EncryptionEnabled"],
            "NodeData": cbt.request.params["NodeData"],
            "TTL": time.time() + self._cm_config["InitialLinkTTL"]
        }
        # Send the message via SIG server to peer node
        remote_act = dict(OverlayId=olid,
                          PeerId=peerid,
                          RecipientCM="LinkManager",
                          Action="LNK_REQ_LINK_ENDPT",
                          Params=json.dumps(msg))

        lcbt = self.create_linked_cbt(cbt)
        lcbt.set_request(self._module_name, "Signal", "SIG_REMOTE_ACTION", remote_act)
        self.submit_cbt(lcbt)
        return  # not returning linkid here, seems not required.

    def create_link_local_endpt(self, cbt):
        # Add to local DS (at recipient) for bookkeeping
        if cbt.request.action == "LNK_REQ_LINK_ENDPT":
            self._lock.acquire()
            params = json.loads(cbt.request.params)
            olid = params["OverlayId"]
            lnkid = params["LinkId"]
            peerid = params["NodeData"]["UID"]
            if self._overlays.get(olid) is None:
                self._overlays[olid] = dict(Peers=dict())
            self._overlays[olid]["Peers"][peerid] = lnkid  # index for quick peer->link lookup
            self._links[lnkid] = dict(Stats=dict())
            self._lock.release()
        lcbt = self.create_linked_cbt(cbt)
        lcbt.set_request(self._module_name, "TincanInterface", "TCI_CREATE_LINK", params)
        self.submit_cbt(lcbt)

    def send_local_link_endpt_to_peer(self, cbt):
        if (not cbt.response.status):
            self.register_cbt("Logger", "LOG_WARNING", "CBT failed {0}".format(cbt.response.data))

        local_cas = cbt.response.data
        parent_cbt = self.get_parent_cbt(cbt)
        if self.get_parent_cbt(cbt).request.action == "LNK_REQ_LINK_ENDPT":
            parent_cbt.set_response(local_cas, True)
            self.complete_cbt(parent_cbt)  # goes back to signal module implicitly, handled by signal.
        elif parent_cbt.request.action == "LNK_CREATE_LINK":
            # handling response after sending TCI_CREATE_LINK with peer_cas
            # create a wrapper method to frame SRA with A = "LNK_ADD_PEER_CAS", dont forget to link with LCL
            msg = copy.deepcopy(cbt.request.params)
            olid = parent_cbt.request.params["OverlayId"]
            peerid = parent_cbt.request.params["PeerId"]
            msg["NodeData"] = {"IP4": "", "UID": "", "MAC": "", "CAS": local_cas, "FPR": ""}
            remote_act = dict(OverlayId=olid,
                              PeerId=peerid,
                              RecipientCM="LinkManager",
                              Action="LNK_ADD_PEER_CAS",
                              Params=json.dumps(msg))
            lcbt = self.create_linked_cbt(parent_cbt)
            lcbt.set_request(self._module_name, "Signal", "SIG_REMOTE_ACTION", remote_act)
            self.submit_cbt(lcbt)
        elif parent_cbt.request.action == "LNK_ADD_PEER_CAS":
            parent_cbt.set_response(data="successful", status=True)
            self.complete(parent_cbt)

    def remove_link(self, cbt):
        olid = cbt.request.params["OverlayId"]
        lid = cbt.request.params["LinkId"]
        self.create_linked_cbt(cbt)
        rl_cbt = self.create_cbt(self._module_name, "TincanInterface",
                                 "TCI_REMOVE_LINK", {"OverlayId": olid, "LinkId": lid})
        self.submit_cbt(rl_cbt)
        # send courtesy terminate link ICC, later.

    def query_link_descriptor(self, cbt):
        pass


    def req_link_descriptors_update(self):
        params = []
        self._lock.acquire()
        for olid in self._overlays:
            params.append(olid)
        self._lock.release()
        self.register_cbt("TincanInterface", "TCI_QUERY_LINK_STATS", params)

    def update_visualizer_data(self, cbt):
        vis_data = dict(LinkManager=dict())
        self._lock.acquire()
        for olid in self._overlays:
            for peerid in self._overlays[olid]["Peers"]:
                lnkid = self._overlays[olid]["Peers"][peerid]
                stats = self._links[lnkid]["Stats"]
                vis_data["LinkManager"][olid] = {lnkid: dict(LinkId=lnkid, PeerId=peerid, Stats=stats)}
        self._lock.release()
        cbt.set_response(data=vis_data, status=True)
        self.complete_cbt(cbt)


    def handle_link_descriptors_update(self, cbt):
        if (not cbt.response.status):
            self.register_cbt("Logger", "LOG_WARNING", "CBT failed {0}".format(cbt.response.data))
            # can this type of error be corrected at runtime?
        else:
            self._lock.acquire()
            for olid in cbt.request.params:
                for lnkid in cbt.response.data[olid]:
                    self._links[lnkid] = dict(Stats=cbt.response.data[olid][lnkid])
            self._lock.release()

    def remote_action_handler(self, cbt):
        if (not cbt.response.status):
            self.register_cbt("Logger", "LOG_WARNING", "CBT failed {0}".format(cbt.response.data))
        else:
            # look inside cbt for inner
            cbt_parent = cbt.parent
            cbt_data = cbt.response.data
            if cbt_data["Action"] == "LNK_REQ_LINK_ENDPT":
                peer_cas = json.loads(cbt_data["Response"])
                olid = cbt_data["OverlayId"]
                lid = cbt_data["LinkId"]
                cbt_load = {"OverlayId": olid, "LinkId": lid,
                            "EncryptionEnabled": cbt_data["EncryptionEnabled"],
                            "NodeData": {
                                "IP4": cbt_data["NodeData"]["IP4"],
                                "UID": cbt_data["NodeData"]["UID"],
                                "MAC": cbt_data["NodeData"]["MAC"],
                                "CAS": peer_cas,
                                "FPR": cbt_data["NodeData"]["FPR"]}}
                lcbt = self.create_linked_cbt(cbt_parent)
                lcbt.set_request(self._module_name, "TincanInterface", "TCI_CREATE_LINK", cbt_load)
                self.submit_cbt(lcbt)
            elif cbt_data["Action"] == "LNK_ADD_PEER_CAS":
                olid = cbt_parent.request.params["OverlayId"]
                peerid = cbt_parent.request.params["PeerId"]
                self._lock.acquire()
                lnkid = self._overlays[olid]["Peers"][peerid]
                self._lock.release()
                cbt_parent.set_response(data={"LinkId": lnkid}, status=True)
                self.complete(cbt_parent)

                # TODO: olid, peerid, linkid should be properly derived for sending post_updates  
                param = {}
                param["UpdateType"] = "ADDED"
                param["OverlayId"] = olid
                param["PeerId"] = peerid
                param["LinkId"] = lnkid
                self._link_updates_publisher.post_update(param)

    def remove_link_handler(self, cbt):
        if (not cbt.response.status):
            self.register_cbt("Logger", "LOG_WARNING", "CBT failed {0}".format(cbt.response.data))
        else:
            # get parent, complete
            parent_cbt = self.get_parent_cbt(cbt)
            # is there a need to set up a response in parent cbt, when do we need to set up a response and when not?
            olid = cbt.request.params["OverlayId"]
            lnkid = cbt.request.params["LinkId"]
            self._lock.acquire()
            # TODO - Remove entry from _overlays
            del(self._links[lnkid])
            self._lock.release()
            parent_cbt.set_response(data="successful", status=True)
            self.complete_cbt(parent_cbt)

            # TODO: Need to remove link from self._links
            # TODO: olid, linkid should be properly derived for sending post_updates
            param = {}
            param["UpdateType"] = "REMOVED"
            param["OverlayId"] = olid
            param["LinkId"] = lid
            self._link_updates_publisher.post_update(param)


    def query_links(self, cbt):
        # categorized by overlay ID's .
        olid = cbt.request.params["OverlayId"]
        peerid = cbt.request.params["LinkId"]
        self._lock.acquire()
        lnkid = self._overlays[olid]["Peers"][peerid]
        cbt.set_response(self._overlays[lnkid]["Stats"], status=True)
        self._lock.release()
        self.complete_cbt(cbt)


    def process_cbt(self, cbt):
        if cbt.op_type == "Request":
            # request CAS, ask peer to create end point and rtesturn cas info after reciving notification.
            if cbt.request.action == "LNK_CREATE_LINK":
                self.req_link_endpt_from_peer(cbt)  # 1 send via SIG

            elif cbt.request.action == "LNK_REQ_LINK_ENDPT":
                self.create_link_local_endpt(cbt)  # 2 rcvd peer req for endpt, send via TCI

            elif cbt.request.action == "LNK_ADD_PEER_CAS":
                self.create_link_local_endpt(cbt)  # 4 rcvd cas from peer, sends via TCI to add peer cas

            elif cbt.request.action == "LNK_REMOVE_LINK":
                self.remove_link(cbt)  # call to Tincan to remove link, cbt should contain olod and link id.

            elif cbt.request.action == "LNK_QUERY_LINKS":  # look into TCI, comes from topology, all link status
                self.query_links(cbt)

            elif cbt.request.action == "SIG_PEER_PRESENCE_NOTIFY":  # probably not going to be used
                pass

            elif cbt.request.action == "VIS_DATA_REQ":
                self.update_visualizer_data(cbt)

            else:
                log = "Unsupported CBT action {0}".format(cbt)
                self.register_cbt("Logger", "LOG_WARNING", log)
        elif cbt.op_type == "Response":
            if cbt.request.action == "SIG_REMOTE_ACTION":
                self.remote_action_handler(cbt)

            elif cbt.request.action == "TCI_CREATE_LINK":
                self.send_local_link_endpt_to_peer(cbt)  # 3/5 send via SIG to peer to update CAS

            elif cbt.request.action == "TCI_REMOVE_LINK":
                self.remove_link_handler(cbt)

            elif cbt.request.action == "TCI_QUERY_LINK_STATS":
                self.handle_link_descriptors_update(cbt)

            self.free_cbt(cbt)

    def timer_method(self):
        self.req_link_descriptors_update()

    def terminate(self):
        pass
