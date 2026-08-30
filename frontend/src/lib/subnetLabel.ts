import type { components } from '@/types/openapi'

type AvailableSubnet = components['schemas']['AvailableSubnet']

function interfaceLabel(interfaceName: string): string {
  if (interfaceName.startsWith('eth') || interfaceName.startsWith('en')) {
    return 'Ethernet'
  }
  if (interfaceName.startsWith('wl')) {
    return 'Wi-Fi'
  }
  return interfaceName
}

export function subnetLabel(subnet: AvailableSubnet): string {
  return `${interfaceLabel(subnet.interface)} · ${subnet.cidr}`
}

export function subnetOptionSuffix(subnet: AvailableSubnet): string | null {
  return subnet.is_default_route ? 'internet connection' : null
}

export function findAvailableSubnet(
  subnets: AvailableSubnet[],
  cidr: string,
): AvailableSubnet | null {
  return subnets.find((subnet) => subnet.cidr === cidr) ?? null
}
