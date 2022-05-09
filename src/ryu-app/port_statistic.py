'''
    In-development.
    This is a Ryu app to monitor network traffic.
'''

# Base
from ryu.base import app_manager
from ryu.app import simple_switch_13
from ryu.base.app_manager import lookup_service_brick
from setting import MONITOR_INTERVAL, DISCOVER_INTERVAL, DELAY_MONITOR, TOPOLOGY_DATA

# Ofp
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.ofproto.ofproto_parser import MsgBase

# Thread
from ryu.lib import hub
from ryu.ofproto import ofproto_v1_3

# Topology Method
from ryu.topology.switches import Switch, Link, Host, Port

# Type hint:
from ryu.controller.controller import Datapath

# Extra
from operator import attrgetter

# External:
from topology_data import TopologyData
from delay_monitor import DelayMonitor

class NetworkMonitor(simple_switch_13.SimpleSwitch13):

    def __init__(self, *args, **kwargs):
        super(NetworkMonitor, self).__init__(*args, **kwargs)
        self.name = 'network_monitor'
        self.topology_api_app = self

        # Get data from another modules.
        self.topology_data: TopologyData = lookup_service_brick(TOPOLOGY_DATA)
        self.delay_monitor: DelayMonitor = lookup_service_brick(DELAY_MONITOR)
        
        # Thread
        self.monitor_thread = hub.spawn(self._monitor_thread)
        # self.measurement_thread = hub.spawn(self._measurement_thread)

        """ _port_stat_reply_handle """
        self.port_stats = {} # {dpid: {port_no:[(packet_count, byte_count, duration_sec, duration_nsec),... ]},... }
        self.delta_port_stats = {} # {dpid: {port_no:[(delta_upload, delta_download, speed, period),... ]},... }
        self.free_bandwidth = {}

        self.stats = {}
        self.port_features = {}

    # Thread:
    def _monitor_thread(self):
        while True:
            self.stats['flow'] = {}
            self.stats['port'] = {}
            
            for dp in self.topology_data.datapaths.values():
                self.port_features.setdefault(dp.id, {})
                self._request_stats(dp)
            print('delta_flow: ') 
            print(self.delta_flow_stats)
            hub.sleep(MONITOR_INTERVAL)

    def _measurement_thread(self):
        while True:
            self._cal_packet_loss()

    def _request_stats(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

        req = parser.OFPPortDescStatsRequest(datapath, 0)
        datapath.send_msg(req)

    #
    def _save_stats(self, _dict, key, value, history_length=2):
        if key not in _dict:
            _dict[key] = []
        _dict[key].append(value)

        if len(_dict[key]) > history_length:
            _dict[key].pop(0)

    def _cal_delta_stat(self, now, pre, period):
        if period: return (now - pre) / (period)
        else: return

    def _save_freebandwidth(self, dpid, port_no, speed):
        # Calculate free bandwidth of port and save it.
        port_state = self.port_features.get(dpid).get(port_no)
        if port_state:
            capacity = port_state[2]
            curr_bw = self._get_free_bw(capacity, speed)
            self.free_bandwidth[dpid].setdefault(port_no, None)
            self.free_bandwidth[dpid][port_no] = curr_bw
        else:
            self.logger.info("Fail in getting port state")
            
    def _create_bandwidth_graph(self):
        pass
    
    def _save_bandwidth_graph(self):
        pass

    def _get_free_bw(self, capacity, speed):
        # BW:Mbit/s
        return max(capacity / 10**3 - speed * 8, 0)

    def _time_coverter(self, sec, nsec):
        return sec + nsec / (10 ** 9)

    def _get_period(self, n_sec, n_nsec, p_sec, p_nsec):
        return self._time_coverter(n_sec, n_nsec) - self._time_coverter(p_sec, p_nsec)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        """
            Save port's stats info
            Calculate port's speed and save it.

            port_stats: {dpid: {port_no:[[packet_count, byte_count, duration_sec, duration_nsec]]}}
            [history][stat_type]
            value is a tuple (tx_bytes, rx_bytes, rx_errors, duration_sec, duration_nsec)
                                0          1          2           3           4
        """
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        self.stats['port'][dpid] = body
        self.free_bandwidth.setdefault(dpid, {})

        for stat in sorted(body, key=attrgetter('port_no')):
            port_no = stat.port_no
            if port_no != ofproto_v1_3.OFPP_LOCAL:

                key = (dpid, port_no)
                value = (stat.tx_bytes, stat.rx_bytes, stat.rx_errors,
                         stat.duration_sec, stat.duration_nsec)

                # Monitoring current port.
                self._save_stats(self.port_stats, key, value, 5)

                port_stats = self.port_stats[key]

                # if len(port_stats) = 1:
                    # prev_stat = 0
                    # period = MONITOR_INTERVAL
                    # continue
                
                if len(port_stats) > 1:
                    curr_stat = port_stats[-1][0] + port_stats[-1][1]
                    prev_stat = port_stats[-2][0] + port_stats[-2][1]

                    period = self._get_period(port_stats[-1][3], port_stats[-1][4],
                                              port_stats[-2][3], port_stats[-2][4])

                    speed = self._cal_delta_stat(curr_stat, prev_stat, period)

                    delta_upload = self._cal_delta_stat(port_stats[-1][0], port_stats[-2][0], period)
                    delta_download = self._cal_delta_stat(port_stats[-1][1], port_stats[-2][1], period)
                    self._save_stats(self.delta_port_stats, key, (delta_upload, delta_download, speed, period), 5)

                    # save free bandwidth (link capacity, can be used for load balancing, calculate link utilization) - Not work in mininet (reason: no link bandwidth)
                    self._save_freebandwidth(dpid, port_no, speed)

    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def port_desc_stats_reply_handler(self, ev):
        """
            Save port description info.
        """
        msg = ev.msg
        dpid = msg.datapath.id
        ofproto = msg.datapath.ofproto

        config_dict = {ofproto.OFPPC_PORT_DOWN: "Down",
                       ofproto.OFPPC_NO_RECV: "No Recv",
                       ofproto.OFPPC_NO_FWD: "No Farward",
                       ofproto.OFPPC_NO_PACKET_IN: "No Packet-in"}

        state_dict = {ofproto.OFPPS_LINK_DOWN: "Down",
                      ofproto.OFPPS_BLOCKED: "Blocked",
                      ofproto.OFPPS_LIVE: "Live"}

        ports = []
        for p in ev.msg.body:
            ports.append('port_no=%d hw_addr=%s name=%s config=0x%08x '
                         'state=0x%08x curr=0x%08x advertised=0x%08x '
                         'supported=0x%08x peer=0x%08x curr_speed=%d '
                         'max_speed=%d' %
                         (p.port_no, p.hw_addr,
                          p.name, p.config,
                          p.state, p.curr, p.advertised,
                          p.supported, p.peer, p.curr_speed,
                          p.max_speed))

            if p.config in config_dict:
                config = config_dict[p.config]
            else:
                config = "up"

            if p.state in state_dict:
                state = state_dict[p.state]
            else:
                state = "up"

            port_feature = (config, state, p.curr_speed)
            self.port_features[dpid][p.port_no] = port_feature

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def _port_status_handler(self, ev):
        """
            Handle the port status changed event.
        """
        msg = ev.msg
        reason = msg.reason
        port_no = msg.desc.port_no
        dpid = msg.datapath.id
        ofproto = msg.datapath.ofproto

        reason_dict = {
            ofproto.OFPPR_ADD: "added",
            ofproto.OFPPR_DELETE: "deleted",
            ofproto.OFPPR_MODIFY: "modified",
        }

        if reason in reason_dict:
            print("switch%d: port %s %s" %
                  (dpid, reason_dict[reason], port_no))
        else:
            print("switch%d: Illeagal port state %s %s" % (port_no, reason))


    """
        Accessor:
        return info as dict
    """
    def get_delta_port_stats(self):
        
        pass
    
    def get_port_stats(self):
        pass
    
# ryu-manager --observe-link --ofp-tcp-listen-port=6633 network_monitor.py
# http://www.muzixing.com/tag/ryu-bandwidth.html