#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Base App:
from setting import FLOW_MANAGER, REST_APP
from ryu.base import app_manager

# WSGI / REST API
import json
from ryu.app.wsgi import WSGIApplication, ControllerBase, Response, route
from ryu.lib import dpid as dpid_lib

# Base Application:
from ryu.controller.controller import Datapath

# WSGI / REST API
import json
from ryu.app.wsgi import WSGIApplication, ControllerBase, Response, route

# External Core
# from simple_swtich_13 import SimpleSwitch13
from delay_monitor import DelayMonitor
from flow_statistic import FlowStatistic
from port_statistic import PortStatistic
from topology_data import TopologyData

# logging

class NetworkStat(app_manager.RyuApp):
    # Version - Context
    _CONTEXTS = {
            'wsgi': WSGIApplication,
            'topology_data': TopologyData,
            'port_statistic': PortStatistic,
            'flow_statistic': FlowStatistic,
            'delay_monitor': DelayMonitor,
            # 'simple_switch': SimpleSwitch13,
            # 'flow_manager': FlowManager,
        }

    def __init__(self, *_args, **_kwargs):
        super(NetworkStat, self).__init__(*_args, **_kwargs)
        self.name = 'controller_rest'
        
        # Register the WSGI application
        wsgi: WSGIApplication = _kwargs['wsgi']
        wsgi.register(NetworkStatRest, {REST_APP: self})

        # External Apps - Load order: alway start the TopologyData first since the other apps depend on it:
        self.topology_data: TopologyData = _kwargs['topology_data']
        self.port_statistic: PortStatistic = _kwargs['port_statistic']
        self.flow_statistic: FlowStatistic = _kwargs['flow_statistic']
        self.delay_monitor: DelayMonitor = _kwargs['delay_monitor']
    
class NetworkStatRest(ControllerBase):

    def __init__(self, req, link, data, **config):
        super(NetworkStatRest, self).__init__(req, link, data, **config)
        self.app: NetworkStat = data[REST_APP]

    @route(REST_APP, '/', methods=['GET'])
    def hello(self, req, **_kwargs):
        body = json.dumps([{'hello': 'world'}])
        return (Response(content_type='application/json', body=body, status=200))
    
    # @route(REST_APP, '/hello/{test}', methods=['GET'])
    # def hello_test(self, req, **_kwargs):
    #     test = _kwargs['test']
    #     body = json.dumps([{'hello': test}])
    #     print(type(test))
    #     return (Response(content_type='application/json', body=body))
    
    # @route(REST_APP, '/json_test', methods=['PUT'])
    # def json_test(self, req, **_kwargs):
    #     try:
    #         content = req.json if req.body else {}
    #     except ValueError:
    #         raise Response(status=400)
    #     # return (Response(content_type='application/json', body=json.dumps(content), status=200))
    #     print(type(content))      
    #     return (Response(content_type='application', body=json.dumps(content), status=200))

    # network info
    @route(REST_APP, '/topology_data', methods=['GET'])
    def topology_data(self, req, **_kwargs):
        hosts, switches, links = self.app.topology_data.get_topology_data()
        topo = {
            'host': hosts,
            'switch': switches,
            'link': links
        }
        body = json.dumps(topo)
        return Response(content_type='application/json', body=body, status=200)

    @route(REST_APP, '/hosts', methods=['GET'])
    def get_hosts(self, req):
        hosts, _, _ = self.app.topology_data.get_topology_data()
        body = json.dumps({'hosts': hosts})
        return Response(content_type='application/json', body=body, status=200)
        
    @route(REST_APP, '/links', methods=['GET'])
    def get_links(self, req):
        _, _, links = self.app.topology_data.get_topology_data()
        body = json.dumps({'link': links})
        return Response(content_type='application/json', body=body, status=200)

    @route(REST_APP, '/switches', methods=['GET'])
    def get_switches(self, req):
        _, switches, _ = self.app.topology_data.get_topology_data()
        body = json.dumps({'switch': switches})
        return Response(content_type='application/json', body=body, status=200)

    # network monitor
    @route(REST_APP, '/port_stat', methods=['GET'])
    def get_port_stat(self, req, **kwargs):
        body = json.dumps(self.app.port_statistic.get_port_stats())
        return Response(content_type='application/json', body=body)
    
    @route(REST_APP, '/delta_port_stat', methods=['GET'])
    def get_delta_port_stat(self, req, **kwargs):
        body = json.dumps(self.app.port_statistic.get_delta_port_stats())
        return Response(content_type='application/json', body=body)

    @route(REST_APP, '/flow_stat', methods=['GET'])
    def get_flow_stat(self, req, **kwargs):
        body = json.dumps(self.app.flow_statistic.get_flow_stats())
        return Response(content_type='application/json', body=body)

    @route(REST_APP, '/delta_flow_stat', methods=['GET'])
    def get_delta_flow_stat(self, req, **kwargs):
        body = json.dumps(self.app.flow_statistic.get_delta_flow_stats())
        return Response(content_type='application/json', body=body)

    # @route(REST_APP, '/port_desc', methods=['GET'])
    # def get_port_desc(self, req, **kwargs):
    #     body = self.app.port_statistic.port_desc.to_json(orient='records')
    #     return Response(content_type='application/json', body=body, status=200)
    
    @route(REST_APP, '/link_quality', methods=['GET'])
    def get_link_quality(self, req, **kwargs):
        """_summary_
        Get link quality data: packet loss, bandwidth, delay
        Returns:
            _type_: json string response
        """
        link_quality = self.app.topology_data.get_link_quality()
        body = json.dumps(link_quality)
        return Response(content_type='application/json', body=body, status=200)
        
# ryu-manager --observe-link --ofp-tcp-listen-port=6633 --wsapi-port=8080 controller_rest.py