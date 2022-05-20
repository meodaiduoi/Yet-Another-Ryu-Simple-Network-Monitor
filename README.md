# Yet-Another-Ryu-Simple-Network-Monitor

YARSNM is a simple network monitor for Ryu focusing on mesuaring network performance. It's able to collect network statistics such as packet loss, bandwidth, latency, speed on each link then expose them to REST API.

| Stat | Unit | Note |
| --- | --- | --- |
| Packetloss | %   |     |
| Delay | ms  |     |
| Link usage | Mbit/s |     |
| Bandwidth | Mbit/s | Don't get bandwidth if you are using mininet. False Value |

And other unprocessed stats like delta_port_stats and delta_flow_stats, port stats and flow stats

## Usage - check out the [wiki](https://github.com/meodaiduoi/Yet-Another-Ryu-Simple-Network-Monitor/wiki)

To start the Monitor use:

```bash
ryu-manager --observe-link --ofp-tcp-listen-port=6633 --wsapi-port=8080 controller_rest.py
```

Start with simple_switch_13 and ofctl_rest.

```bash
ryu-manager --observe-link --ofp-tcp-listen-port=6633 --wsapi-port=8080 ryu.app.simple_switch_13 ryu.app.ofctl_rest controller_rest.py
```

Rest api are all in controller_rest.py, Update on every 3 secs.

## Credit, References:

This is an attemp of me studying SDN network, made to support our research at HUCE. This will not be possible without the source code of those who come before us.

[muzixing/ryu: Li Cheng's self-defined Ryu](https://github.com/muzixing/ryu)

[BenjaminUJun/SDN-measure-project)](https://github.com/BenjaminUJun/SDN-measure-project)

[dodoyuan/SDN-QoS-RYU-APP](https://github.com/dodoyuan/SDN-QoS-RYU-APP/)