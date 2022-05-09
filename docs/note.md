file location
config: /etc/faucet/
log /var/log/faucet/

kill faucet / gauge
pkill -HUP -f faucet.faucet (or faucet.gauge)

faucet lib: /usr/lib/python3/dist-packages/faucet/
/user/bin/python3

check binary location: which faucet (or gauge)

run ryu app: ryu-manager --verbose  ryu.app.ofctl_rest

check site-package location: python3 -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])'

check port:  lsof -i 

prothemus: http://localhost:9090/
grafanas: http://localhost:3000/


tutorial link: http://installfights.blogspot.com/2016/10/mininet-ryu-faucet-gauge-influxdb.html
First, run ryu-manager with faucet app:
ryu-manager --ofp-tcp-listen-port=6633 faucet.faucet ryu.app.simple_switch_13 ryu.app.ofctl_rest
ryu-manager --ofp-tcp-listen-port=6633 --wsapi-port=8081 ryu.app.simple_switch_13 ryu.app.ofctl_rest
ryu-manager --ofp-tcp-listen-port=6633 --wsapi-port=8081 ryu.app.ofctl_rest

To run gauge as a second controller, with a different port, you must run the following code:
ryu-manager --verbose --ofp-tcp-listen-port=6663 faucet.gauge


-- about faucet: http://www.openvswitch.org/support/ovscon2016/8/1450-mysore.pdf
-- faucet playlist: https://www.youtube.com/playlist?list=PL2co5JVVb0LC2rz_Ygyk8OTAnWQCGnh_8

Now, run mininet on other machine (mininet doesn't have an installer for suse) and connect the first switch to both controllers:
-- https://hackmd.io/@pmanzoni/SyWm3n0HH
sudo mn --topo linear,3 --mac --controller remote,ip=localhost,port=6633 --switch ovsk

sudo mn --controller=remote,ip=127.0.0.1,port=6633
sh ovs-vsctl set-controller s1 tcp:$localhost:6633 tcp:localhost:6663

ryu-manager --ofp-tcp-listen-port=6633 --wsapi-port=8080 NetworkStatRest.py 

sudo mn --topo tree,depth=2,fanout=5 --controller=remote,ip=localhost,port=6633 --switch ovsk,protocols=OpenFlow13, --link tc,bw=1,delay=10ms
sudo mn --topo linear,3 --controller=remote,ip=localhost,port=6633 --switch ovsk,protocols=OpenFlow13, --link tc,bw=100,delay=0ms

sudo mn --topo linear,3 --controller=remote,ip=localhost,port=6633 --switch ovsk