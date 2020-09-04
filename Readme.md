# Integration between HA and Openwrt OpenVPN

This component interacts with a Openwrt router OpenVPN component.
It allows to enable/disable VPN's

## HA Configuration

In your configuration.yaml:

```yaml
luci_config:
  host: <openwrt_ip>
  username: !secret openwrt_user
  password: !secret openwrt_password

```

## Openwrt config files (*.uci)

In your HA config folder, create *.uci files with the target Openwrt configuration.  
Each line is an UCI configuration command that will be executed on Openwrt.

Each .uci file will translate into a switch in HA. Triggering the switch will enable the config on Openwrt

ex:

```
#sw_name=wan_static_config
#sw_desc=WAN configuration to box
#sw_test=network.wan.proto
network.wan=interface
network.wan.ifname='eth0.2'
network.wan.proto='static'
network.wan.ipaddr='192.168.254.254'
network.wan.netmask='255.255.255.0'
network.wan.gateway='192.168.254.1'
wireless.default_radio1=wifi-iface
wireless.default_radio1.device='radio1'
wireless.default_radio1.network='lan'
wireless.default_radio1.mode='ap'
wireless.default_radio1.ssid='my_ssid'
wireless.default_radio1.encryption='psk2'
wireless.default_radio1.key='my_password'
```

### Special values:

`#sw_name`: The name of the switch in HA  
`#sw_desc`: Description of the switch  
`#sw_test`: An UCI value uniquely identifying the switch. This allow proper detection of on/off state.  
