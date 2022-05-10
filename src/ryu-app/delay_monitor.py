# Copyright (C) 2016 Li Cheng at Beijing University of Posts
# and Telecommunications. www.muzixing.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ryu.base import app_manager
from ryu.base.app_manager import lookup_service_brick
from ryu.controller import ofp_event

from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3

from ryu.lib import hub
from ryu.topology.switches import Switches, LLDPPacket
import networkx as nx
import time
from setting import DELAY_MONITOR, TOPOLOGY_DATA, DELAY_DETECTING_INTERVAL
from topology_data import TopologyData

class DelayMonitor(app_manager.RyuApp):
    """
        NetworkDelayDetector is a Ryu app for collecting link delay.
    """

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(DelayMonitor, self).__init__(*args, **kwargs)
        self.name = DELAY_MONITOR
        self.sending_echo_request_interval = 0.05
        
        # Get the active object of swicthes and awareness module.
        # So that this module can use their data.
        self.sw_module: Switches = lookup_service_brick('switches')
        self.topology_data: TopologyData = lookup_service_brick('topology_data')

        self.echo_latency = {}
        self.measure_thread = hub.spawn(self._detector)
        
    def _detector(self):
        """
            Delay detecting functon.
            Send echo request and calculate link delay periodically
        """
        while True:
            self._send_echo_request()
            self.create_link_delay()
            self.show_delay_statis()
            hub.sleep(DELAY_DETECTING_INTERVAL)

    def _send_echo_request(self):
        """
            Seng echo request msg to datapath.
        """
        try:
            for datapath in self.topology_data.datapaths.values():
                parser = datapath.ofproto_parser

                data_time = "%.12f" % time.time()
                byte_arr = bytearray(data_time.encode())

                echo_req = parser.OFPEchoRequest(datapath,
                                                 data=byte_arr)
                datapath.send_msg(echo_req)

                # Important! Don't send echo request together, Because it will
                # generate a lot of echo reply almost in the same time.
                # which will generate a lot of delay of waiting in queue
                # when processing echo reply in echo_reply_handler.
                hub.sleep(self.sending_echo_request_interval)
        except self.topology_data is None:
            self.topology_data = lookup_service_brick(TOPOLOGY_DATA)
            return
        
    def _get_delay(self, src, dst):
        """
            Get link delay.
                        Controller
                        |        |
        src echo latency|        |dst echo latency
                        |        |
                   SwitchA-------SwitchB
                        
                    fwd_delay--->
                        <----reply_delay
            delay = (forward delay + reply delay - src datapath's echo latency
        """
        try:
            fwd_delay = self.topology_data.graph[src][dst]['lldpdelay']
            re_delay = self.topology_data.graph[dst][src]['lldpdelay']
            src_latency = self.echo_latency[src]
            dst_latency = self.echo_latency[dst]
            
            delay = (fwd_delay + re_delay - src_latency - dst_latency)/2
            return max(delay, 0)
        except:
            return float('inf')

    def _save_lldp_delay(self, src=0, dst=0, lldpdelay=0):
        try:
            self.topology_data.graph[src][dst]['lldpdelay'] = lldpdelay
        except:
            if self.topology_data is None:
                self.topology_data = lookup_service_brick(TOPOLOGY_DATA)
            return

    def create_link_delay(self):
        """
            Create link delay data, and save it into graph object.
        """
        try:
            for src in self.topology_data.graph:
                for dst in self.topology_data.graph[src]:
                    if src == dst:
                        self.topology_data.graph[src][dst]['delay'] = 0
                        continue
                    delay = self._get_delay(src, dst)
                    self.topology_data.graph[src][dst]['delay'] = delay
        except:
            if self.topology_data is None:
                self.topology_data: TopologyData = lookup_service_brick(TOPOLOGY_DATA)
            return

    @set_ev_cls(ofp_event.EventOFPEchoReply, MAIN_DISPATCHER)
    def _echo_reply_handler(self, ev):
        """
            Handle the echo reply msg, and get the latency of link.
        """
        now_timestamp = time.time()
        try:
            latency = now_timestamp - eval(ev.msg.data)
            self.echo_latency[ev.msg.datapath.id] = latency
        except:
            return
    
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """
            Parsing LLDP packet and get the delay of link.
        """
        msg = ev.msg
        try:
            src_dpid, src_port_no = LLDPPacket.lldp_parse(msg.data)
            dpid = msg.datapath.id
            if self.sw_module is None:
                self.sw_module = lookup_service_brick('switches')

            for port in self.sw_module.ports.keys():
                if src_dpid == port.dpid and src_port_no == port.port_no:
                    delay = self.sw_module.ports[port].delay
                    self._save_lldp_delay(src=src_dpid, dst=dpid,
                                          lldpdelay=delay)
        except LLDPPacket.LLDPUnknownFormat as e:
            return

    def show_delay_statis(self):
        if False and self.topology_data is not None:
            self.logger.info("\nsrc   dst      delay")
            self.logger.info("---------------------------")
            for src in self.topology_data.graph:
                for dst in self.topology_data.graph[src]:
                    if src != dst:
                        delay = self.topology_data.graph[src][dst]['delay']
                        self.logger.info("%s<-->%s : %s" % (src, dst, delay))
                        # self.logger.info(self.topology_data.graph.edges())
            
    """
        Accessor get link delay as dict.
    """        
    def get_link_delay(self):
        pass
    
    