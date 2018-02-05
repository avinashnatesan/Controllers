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

class Icc(ControllerModule):
    def __init__(self, cfx_handle, module_config, module_name):
        super(Icc, self).__init__(cfx_handle, module_config, module_name)
        # Dictionary to hold data about overlayID->peerID->linkID mappings
        self._links = {}
        # Dictionary to hold CBTs created by Icc for remote action requests
        self._remote_acts = {}

    def initialize(self):
        self.register_cbt("Logger", "LOG_INFO", 
                            "{0} Loaded".format(self.module_name))
        
        # Subscribe for link updates notifications from LinkManager
        self._cfx_handle.start_subscription("LinkManager",
                    "LNK_DATA_UPDATES")

    def update_links(self,cbt):
        if cbt.request.params["UpdateType"] == "ADDED":
            olid = cbt.request.params["OverlayId"]
            peerid = cbt.request.params["PeerId"]
            lnkid = cbt.request.params["LinkId"]
            if olid in self._links:
                self._links[olid]["Peers"][peerid] = lnkid
            else:
                self._links[olid] = {}
                self._links[olid]["Peers"] = {}
                self._links[olid]["Peers"][peerid] = lnkid

        elif cbt.request.params["UpdateType"] == "REMOVED":
            olid = cbt.request.params["OverlayId"]
            lnkid = cbt.request.params["LinkId"]
            for peerid in self._links[olid]["Peers"]:
                if self._links[olid]["Peers"][peerid] == lnkid:
                    del self._links[olid]["Peers"][peerid]
                    if self._links[olid]["Peers"][peerid] == {}:
                        del self._links[olid]["Peers"][peerid]
                    if self._links[olid]["Peers"] == {}:
                        del self._links[olid]
                    break

    def send_icc_data(self,cbt):
        """
           cbt.request.params = dict(OverlayId = "",
                                     RecipientId = "",
                                     RecipientCM = "",
                                     Params = opaque_msg) 
        """
        param = {}
        olid = cbt.request.params["OverlayId"]
        peerid = cbt.request.params["RecipientId"]
        param["OverlayId"] = olid
        try:
            param["LinkId"] = self._links[olid]["Peers"][peerid]
            
            lcbt = self.create_linked_cbt(cbt)
            lcbt.set_request("TincanInterface", "TCI_ICC", param)
            self.submit_cbt(lcbt)
        except:
            if overlayid not in self._links:
                self.register_cbt("Logger", "LOG_WARN", 
                    "Non-existent OverlayId ({0}) \
                     for receiving Data".format(overlayid))     
            else:
                self.register_cbt("Logger", "LOG_WARN",
                    "Non-existent PeerId ({0}) in Overlay ({0}) \
                     for receiving Data ".format(peerid, overlayid))

    def broadcast_icc_data(self,cbt):
        peer_list = cbt.request.params["RecipientId"]
        olid = cbt.request.params["OverlayId"]
        for peerid in peer_list:
            param = {}
            param["OverlayId"] = olid
            try:
                param["LinkId"] = self._links[olid]["Peers"][peerid]
                
                lcbt = self.create_linked_cbt(cbt)
                lcbt.set_request("TincanInterface", "TCI_ICC", param)
                self.submit_cbt(lcbt)
            except:
                if overlayid not in self._links:
                    self.register_cbt("Logger", "LOG_WARN", 
                        "Non-existent OverlayId ({0}) \
                         for receiving Broadcast".format(overlayid))
                    break    
                else:
                    self.register_cbt("Logger", "LOG_WARN",
                        "Non-existent PeerId ({0}) in Overlay ({0}) \
                         for receiving Broadcast".format(peerid, overlayid))

    def send_icc_remote_action(self,cbt):
        """
        remote_act = dict(OverlayId="",
                          RecipientId="",
                          RecipientCM="",
                          Action="",
                          Params=json.dumps(opaque_msg),
                          # added by sending Icc
                          InitiatorId="",
                          InitiatorCM="",
                          ActionTag="",
                          # added by responding Icc
                          Data="",
                          Status="")
        """
        rem_act = cbt.request.params
        peerid = rem_act["RecipientId"]
        overlayid = rem_act["OverlayId"]
        try:
            rem_act["LinkId"] = self._links[overlayid]["Peers"][peerid]
            rem_act["InitiatorId"] = self._cm_config["NodeId"]
            rem_act["InitiatorCM"] = cbt.request.initiator
            rem_act["ActionTag"] = cbt.tag
            self.register_cbt("TincanInterface", "TCI_ICC", rem_act)
        except:
            if overlayid not in self._links:
                self.register_cbt("Logger", "LOG_WARN", 
                    "Non-existent OverlayId ({0}) \
                    for receiving Remote action requests".format(overlayid))     
            else:
                self.register_cbt("Logger", "LOG_WARN",
                    "Non-existent PeerId ({0}) in Overlay ({0}) \
                    for receiving Remote action requests".format(peerid, 
                                                            overlayid))     


    def recieve_icc(self,cbt):
        cbt_params = cbt.request.params
        
        # Handling incoming Data requests
        if "ActionTag" not in cbt_params:
            pcbt = self.get_parent_cbt(cbt)
            target_module_name = pcbt.request.params["RecipientCM"]
            msg = pcbt.request.params["Params"]
            self.register_cbt(target_module_name, "ICC_DELIVER_DATA", msg)

        # Handling incoming Remote action requests
        elif cbt_params["ActionTag"] not in self._cfx_handle._pending_cbts:
            target_module_name = cbt_params["RecipientCM"]
            remote_action_code = cbt_params["Action"]
            opaque_msg = cbt_params["Params"]
            rcbt = self.create_cbt("Icc", 
                                    target_module_name, 
                                    remote_action_code, 
                                    opaque_msg)
            self._remote_acts[rcbt.tag] = cbt_params
            self.submit_cbt(rcbt)

        # Handling response to the remote action requests
        else:
            rcbt = self._cfx_handle._pending_cbts[cbt_params["ActionTag"]]
            resp_data = cbt.response.data
            rcbt.set_response(data=resp_data, status=True)
            self.complete_cbt(rcbt)

    def complete_remote_action(self,cbt):
        if cbt.tag in self._remote_acts:
            rem_act = self._remote_acts[cbt.tag]
            olid = rem_act["OverlayId"]
            peerid = rem_act["InitiatorId"]
            lnkid = self._links[olid]["Peers"][peerid]
            rem_act["Data"] = cbt.response.data
            rem_act["Status"] = cbt.response.status
            self.register_cbt("TincanInterface", "TCI_ICC", rem_act)
            self.free_cbt(cbt)

    def process_cbt(self, cbt):
        if cbt.op_type == "Request":
            if cbt.request.action == "LNK_DATA_UPDATES":
                self.update_links(cbt)
                
            elif cbt.request.action == "ICC_SEND_DATA":
                self.send_icc_data(cbt)

            elif cbt.request.action == "ICC_BROADCAST_DATA":
                self.broadcast_icc_data(cbt)

            elif cbt.request.action == "ICC_REMOTE_ACTION":
                self.send_icc_remote_action(cbt)

            elif cbt.request.action == "ICC_RECIEVE":
                self.recieve_icc(cbt)

        elif cbt.op_type == "Response":
            if cbt.request.action == "TCI_ICC":
                self.free_cbt(cbt)
            else:
                self.complete_remote_action(cbt)          

    def terminate(self):
        pass

    def timer_method(self):
        pass