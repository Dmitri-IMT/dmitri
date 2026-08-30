import { describe, expect, it } from 'vitest'
import type { components } from '@/types/openapi'
import {
  findAvailableSubnet,
  subnetLabel,
  subnetOptionSuffix,
} from './subnetLabel'

type AvailableSubnet = components['schemas']['AvailableSubnet']

const ethernetSubnet: AvailableSubnet = {
  interface: 'eth0',
  cidr: '192.168.0.0/24',
  is_default_route: false,
}

const wifiSubnet: AvailableSubnet = {
  interface: 'wlp2s0',
  cidr: '10.12.0.0/16',
  is_default_route: true,
}

describe('subnetLabel', () => {
  it.each([
    ['eth0', 'Ethernet'],
    ['enp0s3', 'Ethernet'],
    ['eno1', 'Ethernet'],
    ['wlan0', 'Wi-Fi'],
    ['wlp2s0', 'Wi-Fi'],
    ['usb0', 'usb0'],
    ['br0', 'br0'],
  ])('maps %s to %s while retaining the CIDR', (interfaceName, label) => {
    expect(subnetLabel({ ...ethernetSubnet, interface: interfaceName })).toBe(
      `${label} · ${ethernetSubnet.cidr}`,
    )
  })
})

describe('subnetOptionSuffix', () => {
  it('labels a default route as the internet connection', () => {
    expect(subnetOptionSuffix(wifiSubnet)).toBe('internet connection')
  })

  it('returns no suffix for another subnet', () => {
    expect(subnetOptionSuffix(ethernetSubnet)).toBeNull()
  })
})

describe('findAvailableSubnet', () => {
  it('returns the reported subnet matching a stored CIDR', () => {
    expect(
      findAvailableSubnet([ethernetSubnet, wifiSubnet], ethernetSubnet.cidr),
    ).toBe(ethernetSubnet)
  })

  it('returns null when the stored CIDR is no longer reported', () => {
    expect(
      findAvailableSubnet([ethernetSubnet, wifiSubnet], '172.16.0.0/16'),
    ).toBeNull()
  })
})
