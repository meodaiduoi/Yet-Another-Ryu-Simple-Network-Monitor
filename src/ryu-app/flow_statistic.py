# Base
from ast import operator
from ryu.base import app_manager
from ryu.base.app_manager import lookup_service_brick
from ryu.ofproto import ofproto_v1_3


from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls, MAIN_DISPATCHER

from ryu.lib import hub
from setting import FLOW_STATISTIC, STATS_REQUEST_INTERVAL, TOPOLOGY_DATA

from topology_data import TopologyData

import operator

class FlowStatistic(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(FlowStatistic, self).__init__(*args, **kwargs)

        self.name = FLOW_STATISTIC

        self.topology_data: TopologyData = lookup_service_brick(TOPOLOGY_DATA)
        
        self.monitor = hub.spawn(self._monitor_thread)
        self.pkl = hub.spawn(self._packet_loss_monitor_thread)
        
        self.flow_stats = {} # {dpid: {(in_port, eth_dst, out_port): [(packet_count, byte_count, duration_sec, duration_nsec),... ]},... }
        self.delta_flow_stats = {} # {dpid: {(in_port, eth_dst, out_port): [(delta_packet, speed),... ]},...  }
        self.packet_loss = {}
        self.link_loss = {}
    
    def _monitor_thread(self):
        while True:
            for dp in self.topology_data.datapaths.values():
                self._request_stats(dp)
            hub.sleep(STATS_REQUEST_INTERVAL)
    
    def _packet_loss_monitor_thread(self):
        while True:
            hub.sleep(4)
            self._get_link_loss()
    
    def _request_stats(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)
    
    def _save_stats(self, _dict, key, value, history_length=2):
        if key not in _dict:
            _dict[key] = []
        _dict[key].append(value)

        if len(_dict[key]) > history_length:
            _dict[key].pop(0)

    def _cal_delta_stat(self, now, pre, period):
        if period: return (now - pre) / (period)
        else: return

    def _get_time(self, sec, nsec):
        return sec + nsec / (10 ** 9)

    def _get_period(self, n_sec, n_nsec, p_sec, p_nsec):
        return self._get_time(n_sec, n_nsec) - self._get_time(p_sec, p_nsec)
    
    # calculate packet loss on link by flow stat:
    def _get_link_loss(self):
        try:
            for src in self.topology_data.graph:
                for dst in self.topology_data.graph[src]:
                    if src == dst:
                        self.topology_data.graph[src][dst]['packet_loss'] = 0
                        continue
                    packet_loss = self._link_loss_match(src, dst)
                    if packet_loss is not None:
                        self.topology_data.graph[src][dst]['packet_loss'] = packet_loss   
        except:
            if self.topology_data is None:
                self.topology_data = lookup_service_brick('topology_data')
            return
        
    def _link_loss_match(self, src_dpid, dst_dpid):
        src_port, dst_port = self.topology_data.get_link_to_port(src_dpid, dst_dpid)
        src_key_list = list(self.delta_flow_stats[src_dpid].keys())
        dst_key_list = list(self.delta_flow_stats[dst_dpid].keys())
        flow_pair = self._flow_pair(src_key_list, dst_key_list, src_port, dst_port)
        return self._cal_link_loss(self.delta_flow_stats, src_dpid, dst_dpid, flow_pair)
        
    def _cal_link_loss(self, delta_flow_stats, src_dpid, dst_dpid, key_pair):
        packet_loss_list = []
        for key in key_pair:
            src_key, dst_key = key
            src_pkt = delta_flow_stats[src_dpid][src_key][-1][0]
            dst_pkt = delta_flow_stats[dst_dpid][dst_key][-1][0]
            
            if src_pkt == 0: continue
            if src_pkt is None or dst_pkt is None: continue
            
            packet_loss = (src_pkt - dst_pkt) / (src_pkt)
            if packet_loss >= 0:
                packet_loss_list.append(packet_loss)
        
        if len(packet_loss_list) == 0: return None
        return sum(packet_loss_list) / len(packet_loss_list)
    
    def _flow_pair(self, src_key, dst_key, src_port_ltp, dst_port_ltp):
        flow_match = []
        for src in src_key:
            _, src_port, eth_src_src, eth_dst_src = src
            for dst in dst_key:
                dst_port, _, eth_src_dst, eth_dst_dst = dst
                if src_port == src_port_ltp and dst_port == dst_port_ltp and \
                   eth_src_src == eth_src_dst and eth_dst_src == eth_dst_dst:
                    flow_match.append((src, dst))
        return flow_match


    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        """
            Save flow stats reply info into self.flow_stats.
            Calculate flow speed and Save it.

            flow_stats: {dpid: { (in_port[(packet_count, byte_count, duration_sec, duration_nsec)]}
            [history][stat_type]
            As: (stat.packet_count, stat.byte_count, stat.duration_sec, stat.duration_nsec)
                        0                 1                 2                 3
        """
        body = ev.msg.body
        dpid = ev.msg.datapath.id

        self.flow_stats.setdefault(dpid, {})
        self.delta_flow_stats.setdefault(dpid, {})

        for stat in sorted([flow for flow in body if flow.priority == 1],
                           key=lambda flow: (flow.match.get('in_port'), flow.match.get('eth_dst'))):

            key = (stat.match['in_port'], stat.instructions[0].actions[0].port,
                   stat.match.get('eth_src'), stat.match.get('eth_dst'))

            value = (stat.packet_count, stat.byte_count,
                     stat.duration_sec, stat.duration_nsec)

            # Monitoring current flow.
            self._save_stats(self.flow_stats[dpid], key, value, 5)
            flow_stats = self.flow_stats[dpid][key]

            if len(flow_stats) == 1:
                self._save_stats(self.delta_flow_stats[dpid], key, (stat.packet_count, stat.byte_count, stat.duration_sec, stat.duration_nsec), 5)

            if len(flow_stats) > 1:
                # for future use
                period = self._get_period(flow_stats[-1][2], flow_stats[-1][3],
                                          flow_stats[-2][2], flow_stats[-2][3])
        
                # Get delta flow stat
                self._save_stats(self.delta_flow_stats[dpid], key, tuple(map(operator.sub, flow_stats[-1], flow_stats[-2])), 5)
    
    def get_flow_stats(self, dpid=None):
        if self.flow_stats is None: return None
        stat = []
        flow_stats = self.flow_stats
        for dpid in flow_stats:
            for flow_name in flow_stats[dpid]:
                in_port, out_port, eth_src, eth_dst = flow_name
                packet_count, byte_count, duration_sec, duration_nsec = flow_stats[dpid][flow_name][-1]
                stat.append({
                    'dpid': dpid,
                    'in_port': in_port,
                    'out_port': out_port,
                    'eth_src': eth_src,
                    'eth_dst': eth_dst,
                    'packet_count': packet_count,
                    'byte_count': byte_count,
                    'duration_sec': duration_sec,
                    'duration_nsec': duration_nsec,
                })
        return stat
    
    def get_delta_flow_stats(self, dpid=None):
        if self.delta_flow_stats is None: return None
        stat = []
        delta_flow_stat = self.delta_flow_stats
        for dpid in delta_flow_stat:
            for flow_name in delta_flow_stat[dpid]:
                in_port, out_port, eth_src, eth_dst = flow_name
                packet_count, byte_count, duration_sec, duration_nsec = self.delta_flow_stats[dpid][flow_name][-1]
                stat.append({
                    'dpid': dpid,
                    'in_port': in_port,
                    'out_port': out_port,
                    'eth_src': eth_src,
                    'eth_dst': eth_dst,
                    'packet_count': packet_count,
                    'byte_count': byte_count,
                    'duration_sec': duration_sec,
                    'duration_nsec': duration_nsec,
                })
        return stat

#  ryu-manager --observe-link --ofp-tcp-listen-port=6633 topology_data.py flow_statistic.py ryu.app.simple_switch_13