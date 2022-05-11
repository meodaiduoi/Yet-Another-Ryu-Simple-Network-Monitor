# Base
from ryu.base import app_manager
from ryu.base.app_manager import lookup_service_brick
from setting import GRAPH_UPDATE_INTERVAL, STATS_REQUEST_INTERVAL, PORT_STATISTIC, TOPOLOGY_DATA

# Ofp
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls, MAIN_DISPATCHER

# Thread
from ryu.lib import hub
from ryu.ofproto import ofproto_v1_3

# Extra
import operator
from operator import attrgetter

# External:
from topology_data import TopologyData

class PortStatistic(app_manager.RyuApp):

    def __init__(self, *args, **kwargs):
        super(PortStatistic, self).__init__(*args, **kwargs)
        self.name = PORT_STATISTIC
        self.topology_api_app = self

        # Get data from another modules.
        self.topology_data: TopologyData = lookup_service_brick(TOPOLOGY_DATA)
        
        # Thread
        self.monitor_thread = hub.spawn(self._monitor_thread)
        self.save_freebandwidth_thread = hub.spawn(self._save_bw_graph)

        """ _port_stat_reply_handle """
        self.port_stats = {} # {(dpid port_no): [(tx_packets, rx_packets ,tx_bytes, rx_bytes, rx_errors, duration_sec, duration_nsec),...]}
        self.delta_port_stats = {} # {(dpid, port_no): [(delta_upload, delta_download, delta_error, period),... ]},... }
        
        """ _create_bandwidth_graph """
        self.free_bandwidth = {} # {dpid: {port_no: (free_bandwidth, usage), ...}, ...}} (Mbit/s)

        """ _port_desc_stats_reply_handler """
        self.port_features = {}

    # Thread:
    def _monitor_thread(self):
        while True:            
            try:
                for dp in self.topology_data.datapaths.values():
                    self.port_features.setdefault(dp.id, {})
                    self._request_stats(dp)
                hub.sleep(STATS_REQUEST_INTERVAL)
            except:
                if self.topology_data is None:
                    self.topology_api_app = lookup_service_brick(TOPOLOGY_DATA)
                    self.logger.info('update topology data')

    def _save_bw_graph(self):
        """
            Save bandwidth data into networkx graph object.
        """
        while True:
            self.graph = self._create_bandwidth_graph(self.free_bandwidth)
            self.logger.debug("save_freebandwidth")
            hub.sleep(GRAPH_UPDATE_INTERVAL)

    # Stat request:
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

    def _get_period(self, n_sec, n_nsec, p_sec, p_nsec):
        to_sec = lambda sec, nsec: sec + nsec / (10 ** 9)
        return to_sec(n_sec, n_nsec) - to_sec(p_sec, p_nsec) # to seconds

    # Bandwidth graph:
    def _save_freebandwidth(self, dpid, port_no, speed):
        # Calculate free bandwidth of port and save it.
        port_state = self.port_features.get(dpid).get(port_no)
        if port_state:
            capacity = port_state[2] / (10**3)  # Kbp/s to MBit/s
            speed = float(speed * 8) / (10**6) # byte/s to Mbit/s
            curr_bw = max(capacity - speed, 0)
            self.free_bandwidth[dpid].setdefault(port_no, None)
            self.free_bandwidth[dpid][port_no] = (curr_bw, speed) # Save as Mbit/s
        else:
            self.logger.warning("Fail in getting port state")
            
    def _create_bandwidth_graph(self, free_bandwidth):
        """
            Save bandwidth data into networkx graph object.
        """
        try:
            graph = self.topology_data.graph
            link_to_port = self.topology_data.link_to_port
            for link in link_to_port:
                (src_dpid, dst_dpid) = link
                (src_port, dst_port) = link_to_port[link]
                if src_dpid in free_bandwidth and dst_dpid in free_bandwidth:
                    src_free_bandwidth, src_link_usage = free_bandwidth[src_dpid][src_port]
                    dst_free_bandwidth, dst_link_usage = free_bandwidth[dst_dpid][dst_port]
                    
                    bandwidth = min(src_free_bandwidth, dst_free_bandwidth)
                    link_usage = min(src_link_usage, dst_link_usage)
                
                    # add key:value of bandwidth into graph.
                    graph[src_dpid][dst_dpid]['free_bandwith'] = bandwidth
                    graph[src_dpid][dst_dpid]['link_usage'] = link_usage 
                    # graph[src_dpid][dst_dpid]['link_utilization'] = None
                    
                else:
                    graph[src_dpid][dst_dpid]['bandwidth'] = 0
                    graph[src_dpid][dst_dpid]['link_usage'] = 0
            return graph
        except:
            self.logger.info("Create bw graph exception")
            if self.topology_data is None:
                self.topology_data = lookup_service_brick(TOPOLOGY_DATA)
            return self.topology_data.graph

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        """
            Save port's stats info
            Calculate port's speed and save it.

            port_stats: {(dpid port_no): [(tx_packets, rx_packets ,tx_bytes, rx_bytes, rx_errors, duration_sec, duration_nsec),...]}
            [history][stat_type]
            value is a tuple (tx_packets, rx_packets ,tx_bytes, rx_bytes, rx_errors, duration_sec, duration_nsec)
                                  0          1           2         3          4           5             6         
        """
        body = ev.msg.body
        dpid = ev.msg.datapath.id
    
        self.free_bandwidth.setdefault(dpid, {})

        # !FIXME: add rx_packets
        for stat in sorted(body, key=attrgetter('port_no')):
            port_no = stat.port_no
            if port_no != ofproto_v1_3.OFPP_LOCAL:

                key = (dpid, port_no)
                value = (stat.tx_packets, stat.rx_packets, stat.tx_bytes, stat.rx_bytes,
                         stat.rx_errors, stat.duration_sec, stat.duration_nsec)

                # Monitoring current port.
                self._save_stats(self.port_stats, key, value, 5)

                port_stats = self.port_stats[key]

                if len(port_stats) == 1:
                    self._save_stats(self.delta_port_stats, key, (stat.tx_packets, stat.rx_packets, stat.tx_bytes, stat.rx_bytes, stat.rx_errors, stat.duration_sec, STATS_REQUEST_INTERVAL), 5)
                
                if len(port_stats) > 1:
                    curr_stat = port_stats[-1][2] + port_stats[-1][3]
                    prev_stat = port_stats[-2][2] + port_stats[-2][3]

                    period = self._get_period(port_stats[-1][5], port_stats[-1][6],
                                              port_stats[-2][5], port_stats[-2][6])

                    speed = self._cal_delta_stat(curr_stat, prev_stat, period)
                    
                    # Using maping to save detal_port_stats.
                    self._save_stats(self.delta_port_stats, key, tuple(map(operator.sub, port_stats[-1], port_stats[-2])), 5)

                    # save free bandwidth (link capacity, can be used for load balancing, calculate link utilization) - Not work in mininet (reason: no link bandwidth)
                    self._save_freebandwidth(dpid, port_no, speed)

    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def _port_desc_stats_reply_handler(self, ev):
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
    def get_port_stats(self):
        if self.port_stats is None: return None
        stats = []
        port_stats = self.port_stats
        for dpid, port_no in port_stats:
            tx_packtes, rx_packets, tx_bytes, rx_bytes, rx_errors, duration_sec, duration_nsec = port_stats[(dpid, port_no)][-1]
            stats.append({
                'dpid': dpid,
                'port_no': port_no,
                'tx_packets': tx_packtes,
                'rx_packets': rx_packets,
                'tx_bytes': tx_bytes,
                'rx_bytes': rx_bytes,
                'rx_error': rx_errors,
                'durration_sec': duration_sec,
                'duration_nsec': duration_nsec
            })
        return stats    

    def get_delta_port_stats(self):
        if self.delta_port_stats is None: return None
        stats = []
        delta_port_stats = self.delta_port_stats
        for dpid, port_no in delta_port_stats:
            tx_packtes, rx_packets, tx_bytes, rx_bytes, rx_errors, duration_sec, duration_nsec = delta_port_stats[(dpid, port_no)][-1]
            stats.append({
                'dpid': dpid,
                'port_no': port_no,
                'tx_packets': tx_packtes,
                'rx_packets': rx_packets,
                'tx_bytes': tx_bytes,
                'rx_bytes': rx_bytes,
                'rx_error': rx_errors,
                'durration_sec': duration_sec,
                'duration_nsec': duration_nsec
            })
        return stats
    
    def show_stat(self):
        if True and self.topology_data is not None:
            # self.logger.info(self.topology_data.graph.edges(data=True))
            pass

# sudo mn --topo linear,4 --controller=remote,ip=localhost,port=6633 --switch ovsk --link tc,bw=0.1,delay=0ms,loss=10
# ryu-manager --observe-link --ofp-tcp-listen-port=6633 topology_data.py port_statistic.py
# http://www.muzixing.com/tag/ryu-bandwidth.html