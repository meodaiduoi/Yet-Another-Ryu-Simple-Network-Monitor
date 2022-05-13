#!/usr/bin/env python

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSController
from mininet.node import CPULimitedHost, Host, Node
from mininet.node import OVSKernelSwitch, UserSwitch
from mininet.node import IVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink, Intf
from subprocess import call
import numpy as np
from numpy import random
import json
import time
import pandas as pd

import requests
from requests.auth import HTTPBasicAuth
import random

def myNetwork():

    net = Mininet( topo=None,
                   build=False,
                   ipBase='10.0.0.0/8')

    info( '*** Adding controller\n' )
    c0=net.addController(name='c0',
                      controller=RemoteController,
                      ip='10.20.0.209',
                      protocol='tcp',
                      port=6633)
    # c1=net.addController(name='c1',
    #                   controller=RemoteController,
    #                   ip='192.168.0.108',
    #                   protocol='tcp',
    #                   port=6653)


    info( '*** Add switches\n')
    s1 = net.addSwitch('s1', cls=OVSKernelSwitch)
    s2 = net.addSwitch('s2', cls=OVSKernelSwitch)
    s3 = net.addSwitch('s3', cls=OVSKernelSwitch)
    s4 = net.addSwitch('s4', cls=OVSKernelSwitch)
    s5 = net.addSwitch('s5', cls=OVSKernelSwitch)
    s6 = net.addSwitch('s6', cls=OVSKernelSwitch)
    s7 = net.addSwitch('s7', cls=OVSKernelSwitch)
    s8 = net.addSwitch('s8', cls=OVSKernelSwitch)


    info( '*** Add hosts\n')
    h1 = net.addHost('h1', cls=Host, ip='10.0.0.1', defaultRoute=None)
    h2 = net.addHost('h2', cls=Host, ip='10.0.0.2', defaultRoute=None)  
    h3 = net.addHost('h3', cls=Host, ip='10.0.0.3', defaultRoute=None)
    h4 = net.addHost('h4', cls=Host, ip='10.0.0.4', defaultRoute=None)
    h5 = net.addHost('h5', cls=Host, ip='10.0.0.5', defaultRoute=None)
    h6 = net.addHost('h6', cls=Host, ip='10.0.0.6', defaultRoute=None)
    h7 = net.addHost('h7', cls=Host, ip='10.0.0.7', defaultRoute=None)
    h8 = net.addHost('h8', cls=Host, ip='10.0.0.8', defaultRoute=None)

    info( '*** Add links\n')
    # add link between si vs hi

    # bw-10Gb/s
    net.addLink(s1, h1, bw=10, delay='5ms', loss=4, use_htb=True)
    net.addLink(s1, h2, bw=10, delay='5ms', loss=4, use_htb=True)
    net.addLink(s2, h3, bw=10, delay='5ms', loss=4, use_htb=True)
    net.addLink(s2, h4, bw=10, delay='5ms', loss=4, use_htb=True)

    # add link vs servert
    net.addLink(s4, h5, bw=10, delay='5ms', loss=4, use_htb=True)
    net.addLink(s4, h6, bw=10, delay='5ms', loss=4, use_htb=True)
    net.addLink(s5, h7, bw=10, delay='5ms', loss=4, use_htb=True)
    net.addLink(s5, h8, bw=10, delay='5ms', loss=4, use_htb=True)

    # add link between si and si+1
    net.addLink(s1, s2, bw=10, delay='5ms', loss=4, use_htb=True)
    net.addLink(s2, s3, bw=10, delay='5ms', loss=4, use_htb=True)
    net.addLink(s3, s4, bw=10, delay='5ms', loss=4, use_htb=True)
    net.addLink(s4, s1, bw=10, delay='5ms', loss=4, use_htb=True)


    net.addLink(s5, s6, bw=10, delay='5ms', loss=4, use_htb=True)
    net.addLink(s6, s7, bw=10, delay='5ms', loss=4, use_htb=True)
    net.addLink(s7, s8, bw=10, delay='5ms', loss=4, use_htb=True)
    net.addLink(s8, s5, bw=10, delay='5ms', loss=4, use_htb=True)
    
    net.addLink(s4, s5, bw=10, delay='5ms', loss=4, use_htb=True)
    net.addLink(s3, s7, bw=10, delay='5ms', loss=4, use_htb=True)
    net.addLink(s1, s6, bw=10, delay='5ms', loss=4, use_htb=True)


    info( '*** Starting network\n')
    net.build()
    info( '*** Starting controllers\n')
    for controller in net.controllers:
        controller.start()

    info( '*** Starting switches\n')
    net.get('s1').start([c0])
    net.get('s2').start([c0])
    net.get('s3').start([c0])
    net.get('s4').start([c0])
    net.get('s5').start([c0])
    net.get('s6').start([c0])
    net.get('s7').start([c0])
    net.get('s8').start([c0])

    info( '*** Post configure switches and hosts\n')

    # net.pingAll()
    # #time.sleep(15)
    # # generate topo
    # generate_topo(net)

    CLI(net)
    net.stop()

def generate_topo(net):

    host_list, server_list = create_host_server(net)
    num_host = len(host_list)   

    period = 20 # random data from 0 to period 
    interval = 5 # each host generates data 5 times randomly

    # khoi tao bang thoi gian cho tung host
    print("bang khoi tao")
    starting_table = create_starting_table(num_host, period, interval)
    print("\n")
    print("Bang ket thuc")
    processing_table = create_processing_table(num_host, period, starting_table, interval)

    write_table_to_file(starting_table, 'starting_table.csv')
    write_table_to_file(processing_table, 'processing_table.csv')

    # kich hoat server chuan bi lang nghe su dung iperf

    # chay topo mininet
    # bat reactive
    # khi nao print bat flask thi bat
    # sau do doi tin hieu reponse
    start_server(host_list, server_list, net)
    print("Tuan bat flask")
    # delay de chay flask da roi lap lich goi flask api
    time.sleep(20)


    # lap lich cho host
    run_shedule(starting_table, processing_table, period, interval,net)

    #call_routing_api(host_list, server_list)

    

def create_starting_table(num_host, period, interval):

    starting_table =  np.zeros( (num_host, interval) )
    s = 0 # random starting time

    for h in range( len(starting_table) ):
        for t in range( len(starting_table[h]) ):
            s = random.uniform(0, period) # do t = 0 to 100

            starting_table[h][t] = s
        starting_table[h].sort()

    print(starting_table)
    return starting_table

def create_processing_table(num_host, period, starting_table, interval):

   processing_table = np.zeros( (num_host, interval) )
   s = 0 # processing time
     
   for h in range( len(processing_table) ):
        for t in range( len(processing_table[h]) ):
          if t == len(processing_table[h]) - 1:
                      upper_bound = period   
          else:
                      upper_bound = starting_table[h][t+1]

          # thoi gian chay moi host thuoc khoang denta thoi gian 
          # bat dau t va t+1 cua host do  
          low_bound   = starting_table[h][t]
          s = random.uniform(low_bound, upper_bound)  
          #print("L = ", low_bound, "Upper = ", upper_bound, "value = ", s)  
          processing_table[h][t] = s

   print(processing_table)
   return processing_table   

def run_shedule(starting_table, processing_table, period, interval, net):

    visited = np.full( ( len(starting_table), interval), False, dtype=bool )
    visited_stop = np.full( ( len(processing_table), interval), False, dtype=bool )
    dem = 0
    dem_stop = 0
    begin= time.time()
    # ban dau current la moc 0
    current= float(time.time() - begin) # giay hien tai - giay goc = giay current tai moc 0
    #counter time
    counter=float(period+3) # theo doi trong n giay period
    print("print ok after "+str(counter)+"s")

    while(counter-float(current)>0.001): #quan sat trong 10s
        current = time.time() - begin
        #print("current = ", current)
        for host in range ( len(starting_table) ):
            for t in range ( len(starting_table[host])):
                # sai so be hon 0.001
                if  abs (starting_table[host][t] - current ) < 0.001 and visited[host][t] == False:
                    #print("host = ", host, "time = ", t)
                    #des=call_routing_api_flask(host+1)
                    p=net.get('h%s' %(host+1))
                    #print( p.IP() )
                    des=call_routing_api_flask( p.IP() )
                    #des = '10.0.0.%s' %des
                    # truyen data den ip cua dest voi duration = 60s
                    #print("TRUYEN DU LIEU ", p.IP(), "--->", des)
                    plc_cmd = 'iperf -c %s -p 1337 -t 1000 &' %des
                    p.cmd(plc_cmd)   
                    print(plc_cmd)
                    print("host", host, " --> ", des, "tai giay thu", starting_table[host][t])
                    dem += 1
                    visited[host][t] = True
        
        # for host in range( len(processing_table)):
        #     for stop in range (len(processing_table[host])):
        #         if  abs (processing_table[host][stop] - current ) < 0.001 and visited_stop[host][stop] == False:
        #             #print("host = ", host, "stop= ", stop)
        #             print("host", host, " stop", "tai giay thu", processing_table[host][stop])
        #             visited_stop[host][stop] = True
        #             dem_stop += 1

        # if abs (period - current) < 0.01:
        #     print("host", host, "stop tai giay thu", period )

            
    print("ok")
    print("Dem = " , dem)
    # print("dem stop", dem_stop)
      
def write_table_to_file(table, name_file):

    # convert table into dataframe
    df = pd.DataFrame(table)
    
    # save the dataframe as a csv file
    df.to_csv(name_file)
    
def create_host_server(net):

    # ban dau tap net.hosts co 1,2 ... 8 con
    host_list = []
    server_list = []

    for h in range( len(net.hosts) ):
        if h <=3:   # host 1 2 3 4 
            host_list.append( net.hosts[h])
        else: # server  5 6 7 8
            server_list.append( net.hosts[h])

    return (host_list, server_list)

def call_routing_api_flask(host):
    print("call flask")
    # des=8
    # url = 'http://127.0.0.1:5000/getIpServer/'
    # response = requests.post(url)

    response = requests.post("http://127.0.0.1:5000/getIpServer", data= host)

    
    dest_ip = response.text
    #print(dest_ip)
    return str(dest_ip)

    # minh phai doc duoc topo mininet
    # sau do moi bat flask
    # sau do file mininet moi chay iperf lap lich


 
    # response = requests.post('http://localhost:8181/onos/v1/flows?appId=onos.onosproject.routing', data = host)
    # print(response)

    # goi url flask
    #return des

def call_routing_api(host_list, server_list):
    
    query = {'src':'10.0.0.1', 'dst':'10.0.0.8'}
    response = requests.get('http://localhost:8181/onos/test/localTopology/set-Routing-byIp', 
    params=query,auth=HTTPBasicAuth('onos', 'rocks'))
    print(response)

def start_server(host_list, server_list, net):

    p1, p2, p3,p4,p5,p6,p7,p8 = net.get('h1', 'h2', 'h3','h4', 'h5', 'h6','h7', 'h8')

    plc1_cmd=''
    strGet=''
    plc2_cmd=''
    i=4
    # duyet qua 8 host
    while i < 8:
        # moi lan khoi tao 1 server co khoang nghi giua chung
        #interval = random.uniform(0.01, 0.1)
        #print ("Initialized transfer; waiting %f seconds..." % interval)
        #time.sleep(interval)

        # do host chay tu 1 nen tang bien i len 1 
        #p5.cmd(plc1_cmd)
        i=i+1

        # ping host i
        plc1_cmd='ping -c5 10.0.0.%s' % i
        print(plc1_cmd)

        # get ten host i 
        strGet='h%s' % i
        print(strGet)
        p=net.get(strGet)

        # kich hoat host i la server, monitor moi 1s
        plc2_cmd = 'iperf -s -p 1337 -i 1 &'
        p.cmd(plc2_cmd)

    # transfer_data(net)

def transfer_data(net):
    print("tam dung 5s")
    time.sleep(5)
    i=0
    j = 0
  
    while j < 3:
            # h1,.. h4 la client, h5 -> h8 la server
            while i < 4:
                    # moi lan rou tu src -> dst se co 1 khoang nghi
                    i=i+1
                    interval = random.uniform(0.01, 0.1)
                    print("prepare for Routing about", interval, "seconds")
                    # time.sleep(interval)
                    time.sleep(5)

                    # random server 5 -> 8
                    ip_dest = random.randint(5, 8)
                    # call api routing
                    query = {'src':'10.0.0.%s' %i, 'dst':'10.0.0.%s' %ip_dest}
                    response = requests.get('http://localhost:8181/onos/test/localTopology/set-Routing-byIp', params=query,auth=HTTPBasicAuth('onos', 'rocks'))
                    print("Routing from host", i, " to server ", ip_dest)
                    print(response)

                    # sau khi co duong di thi ta goi iperf de truyen data from source -> dest
                    p=net.get('h%s' %i)
                    ip_dest = '10.0.0.%s' %ip_dest
                    # truyen data den ip cua dest voi duration = 60s
                    plc_cmd = 'iperf -c %s -p 1337 -t 60 &' %ip_dest
                    p.cmd(plc_cmd)   
                    print(plc_cmd)
                    print("Tranfering from host thu", i, "to", ip_dest)
                    print("\n")
            j = j+1
       
    print('Kiem tra')
if __name__ == '__main__':
    setLogLevel( 'info' )
    myNetwork()
    # sudo mn -c
    # sudo python3 -E example2.py
