# Integration between HA and Openwrt OpenVPN

This component interacts with a Openwrt router OpenVPN component.
It allows to enable/disable VPN's

# Configuration

In your configuration.yaml:

```
luci_config:
  host: <openwrt_ip>
  username: !secret openwrt_user
  password: !secret openwrt_password

```