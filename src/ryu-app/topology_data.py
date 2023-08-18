# Base:
from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3

# event:
from ryu.controller.handler import set_ev_cls
from ryu.topology import event
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER

# Topology
from ryu.controller.controller import Datapath
from ryu.topology.api import get_link, get_switch, get_host, get_all_switch, get_all_host, get_all_link
from ryu.topology.switches import Switch, Link, Host, Port

from setting import TOPOLOGY_DATA, DISCOVER_INTERVAL

# Thread:
from ryu.lib import hub

# Graph:
import networkx as nx

class TopologyData(app_manager.RyuApp):
    
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    
    def __init__(self, *_args, **_kwargs):
        super(TopologyData, self).__init__(*_args, **_kwargs)
        self.name = TOPOLOGY_DATA
        self.topology_api_app = self
        
        # Threads
        self.discover_thread = hub.spawn(self._discover_thread)
        
        # datapath:
        self.datapaths: dict[Datapath.id, Datapath] = {}  # Store switch in topology using OpenFlow
                
        # Link and switch
        self.switches = []
        self.access_table = {}       # {(sw,port) :(ip, mac)}
        self.switch_port_table = {}  # dpip->port_num
        self.access_ports = {}       # dpid->port_num
        self.interior_ports = {}     # {dpid: {port_num,...},...} - port_num is set of ports connected to other switches
        self.link_to_port = {}       # {(src.dpid, dst.dpid): (src.port_no, dst.port_no)}
        
        # Network Graph:
        self.graph = nx.DiGraph()
        
    def _discover_thread(self):
        while True:
            hub.sleep(DISCOVER_INTERVAL)
    
    def _get_graph(self, link_list):
        """
            Get Adjacency matrix from link_to_port
        """
        for src in self.switches:
            for dst in self.switches:
                if src == dst:
                    self.graph.add_edge(src, dst, weight=0)
                elif (src, dst) in link_list:
                    self.graph.add_edge(src, dst, weight=1)
        return self.graph
    
    def _create_port_map(self, switch_list):
        """
            Create interior_port table and access_port table.
        """
        for sw in switch_list:
            dpid = sw.dp.id
            self.switch_port_table.setdefault(dpid, set())
            self.interior_ports.setdefault(dpid, set())
            self.access_ports.setdefault(dpid, set())

            for p in sw.ports:
                self.switch_port_table[dpid].add(p.port_no)

    def _create_access_ports(self):
        """
            Get ports without link into access_ports
        """
        for sw in self.switch_port_table:
            all_port_table = self.switch_port_table[sw]
            interior_port = self.interior_ports[sw]
            self.access_ports[sw] = all_port_table - interior_port

    
    def _create_interior_links(self, link_list):
        """
            Get links source port to dst port from link_list,
            link_to_port:(src_dpid,dst_dpid)->(src_port,dst_port)
        """
        for link in link_list:
            src = link.src
            dst = link.dst
            self.link_to_port[(src.dpid, dst.dpid)] = (src.port_no, dst.port_no)

            # Find the access ports and interiorior ports
            if link.src.dpid in self.switches:
                self.interior_ports[link.src.dpid].add(link.src.port_no)
            if link.dst.dpid in self.switches:
                self.interior_ports[link.dst.dpid].add(link.dst.port_no)
    
    @set_ev_cls([event.EventSwitchEnter,
                 event.EventSwitchLeave, event.EventPortAdd,
                 event.EventPortDelete, event.EventPortModify,
                 event.EventLinkAdd, event.EventLinkDelete])        
    def _get_topology(self, ev):
        switch_list = get_switch(self.topology_api_app, None)
        self._create_port_map(switch_list)
        self.switches = self.switch_port_table.keys()
        links = get_link(self.topology_api_app, None)
        self._create_interior_links(links)
        self._create_access_ports()
        self._get_graph(self.link_to_port.keys())

    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]

    '''
        accessor api:
    '''
    def get_link_to_port(self, src_dpid, dst_dpid):
        if (src_dpid, dst_dpid) in self.link_to_port:
            return self.link_to_port[(src_dpid, dst_dpid)]
        else:
            self.logger.info("dpid:%s->dpid:%s is not in links" % (src_dpid, dst_dpid))
            return None
    
    def is_in_interior_ports(self, dpid, port_num):
        if port_num in self.interior_ports[dpid]: return True
        return False
    
    def get_interior_ports(self, dpid):
        if dpid in self.interior_ports:
            return self.interior_ports[dpid]
        else:
            self.logger.info("dpid:%s is not in interior_ports" % dpid)
            return None

    def get_topology_data(self):
        """_summary_
            Get topology data for the REST API
        Returns:
            A dict of topology data
            _type_: dict
        """
        return self.get_host(), self.get_switch(), self.get_link()
    
    # Rollback in case something caught fire
    def get_host(self):
        """
            Return host data for the REST API
        Returns:
            An array of dict about hosts data
        """
        host_list = get_all_host(self)

        # To remove hosts that are not removed by controller
        ports = []
        # NOTE: unify this section later ----
        switches = get_all_switch(self)
        for switch in switches:
            ports += switch.ports
        port_macs = [p.hw_addr for p in ports]
        n_host_list = [h for h in host_list if h.port.hw_addr in port_macs]
        hosts_dict = [h.to_dict() for h in n_host_list]
        # ----
        sw_list = self.get_switch()
        hosts_dict = [h.to_dict() for h in host_list]
        hw_addrs = [port['hw_addr'] for switch in sw_list for port in switch['ports']]
        hosts_dict = [host for host in hosts_dict if host['mac'] not in hw_addrs]
        return hosts_dict
    
    # New shinny func
    # def get_host(self):
    #     """
    #         Return host data for the REST API
    #     Returns:
    #         An array of dict about hosts data
    #     """
    #     host_list = get_all_host(self)
    #     hostdict_list = [h.to_dict() for h in host_list]
    #     swdict_list = self.get_switch()
        
    #     # To remove hosts that are not removed by controller
    #     ports = [port for switch in swdict_list for port in switch['ports']]
    #     port_macs  = [p['hw_addr'] for p in ports]
    #     hostdict_list = [h for h in hostdict_list if h['port']['hw_addr'] in port_macs]
        
    #     # To remove host that has mac is hw_addr of switch port
    #     hw_addrs = [port['hw_addr'] for switch in swdict_list for port in switch['ports']]
    #     hostdict_list = [host for host in hostdict_list if host['mac'] not in hw_addrs]
    #     return hostdict_list
            
        
    def get_switch(self):
        '''
            Return switch data for the REST API
        Returns:
            An array of dict about switch data
        '''
        switches: list[Switch] = get_all_switch(self)
        return [switch.to_dict() for switch in switches]
        
    
    def get_link(self):
        '''
            Return array of links dict for the REST API
        Returns:
            An array of dict about links data
        '''
        links: list[Link] = get_all_link(self)
        return [link.to_dict() for link in links]
    
    def get_link_quality(self):
        """_summary_
            Get link quality data for the REST API
        Returns:
            A dict of link graph data structure
        """
        link_quality = []
        for src, dst, value in self.graph.edges(data=True):
            if src != dst:
                
                # I wish i understood Lambda function
                packet_loss = value.get('packet_loss', None)
                delay = value.get('delay', None)
                link_usage = value.get('link_usage', None)
                free_bandwith = value.get('free_bandwith', None)
                link_quality.append({
                    'src.dpid': src,
                    'dst.dpid': dst,
                    'delay': delay,
                    'packet_loss': packet_loss,
                    'link_usage': link_usage,
                    'free_bandwidth': free_bandwith
                })
        return link_quality
    
    def get_topology_graph(self):
        """
            Dump json topology 
        """
        return nx.json_graph.node_link_data(self.graph)

    