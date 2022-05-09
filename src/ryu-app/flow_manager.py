from ryu.app import simple_switch_13
from ryu.base import app_manager
from ryu.controller.controller import Datapath

# Flow Mod Managerment
from ryu.ofproto.ofproto_v1_3 import OFPG_ANY
from ryu.topology import event, switches

from ryu.controller import dpset

class FlowManager(simple_switch_13.SimpleSwitch13):

    def __init__(self, *args, **kwargs):
        super(FlowManager, self).__init__(*args, **kwargs)

    '''
        Swtich functions
    '''

    def flow_add(self,
                 dpid,
                 in_port,
                 eth_dst,
                 cookie=0,
                 cookie_mask=None,
                 table_id=0,
                 idle_timeout=0,
                 hard_timeout=None,
                 priority=32768,
                 buffer_id=None):
        datapath = self.datapaths[dpid]
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        if cookie_mask == None: cookie_mask = cookie
        if hard_timeout == None: hard_timeout = idle_timeout
        if buffer_id == None: buffer_id = ofproto.OFP_NO_BUFFER

        match = parser.OFPMatch(in_port=in_port, eth_dst=eth_dst)
        actions = [parser.OFPActionOutput(ofproto.OFPP_NORMAL, 0)]
        instructions = [
            parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)
        ]

        flow_mod = datapath.parser.OFPFlowMod(
            datapath, cookie, cookie_mask, table_id, ofproto.OFPFC_ADD,
            idle_timeout, hard_timeout, priority, buffer_id, ofproto.OFPP_ANY,
            ofproto.OFPG_ANY, ofproto.OFPFF_SEND_FLOW_REM, match, instructions)
        datapath.send_msg(flow_mod)

    def flow_del(self, dpid, table_id=None):
        datapath = self.datapaths[dpid]

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        if table_id == None: table_id = ofproto.OFPTT_ALL
        match = parser.OFPMatch()
        instructions = []

        flow_mod = parser.OFPFlowMod(datapath, 0, 0, table_id,
                                     ofproto.OFPFC_DELETE, 0, 0, 1,
                                     ofproto.OFPCML_NO_BUFFER,
                                     ofproto.OFPP_ANY, OFPG_ANY, 0, match,
                                     instructions)
        datapath.send_msg(flow_mod)

    def flow_clear_all(self):
        for dpid, _ in self.datapaths:
            self.flow_del(dpid)

    def get_flow(self, dpid=None):
        pass
