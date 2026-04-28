// TEMPORÁRIO
import type { Device, Finding, Scan, Severity } from "../types";

export const SEV_ORDER: Record<Severity, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export const fmtDate  = (iso: string) => new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
export const fmtShort = (iso: string) => new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
export const shortId  = (uuid: string) => uuid.slice(0, 8);
export const timeAgo  = (iso: string) => {
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return 'há menos de 1h';
  if (h < 24) return `há ${h}h`;
  return `há ${Math.floor(h / 24)} dias`;
};

export const SCANS: Scan[] = [
  {
    scan_id: "scan-001",
    timestamp: "2026-01-01T12:00:00.000Z",
    subnet: "10.0.0.0/24",
    scan_mode: "quick",
    status: "completed",
    device_count: 5,
    finding_count: 2,
    highest_severity: "medium",
    metadata: {
      agent_version: "v0.0.0",
      nmap_arguments: "-sV",
      elapsed_seconds: 42
    }
  }
];

export const DEVICES: Device[] = [
  {
    ip: "10.0.0.1",
    mac: "AA:BB:CC:DD:EE:01",
    hostname: "gateway.local",
    vendor: "Generic Vendor A",
    ports: [
      { port: 80, protocol: "tcp", state: "open", service: "http", version: "Generic HTTP Server" }
    ],
    last_seen_at: "2026-01-01T12:00:00.000Z",
    device_id: "dev-001",
    first_seen_at: "2026-01-01T12:00:00.000Z",
    open_ports_count: 1,
    highest_severity: "low"
  },
  {
    ip: "10.0.0.10",
    mac: "AA:BB:CC:DD:EE:02",
    hostname: "device-10.local",
    vendor: "Generic Vendor B",
    ports: [
      { port: 22, protocol: "tcp", state: "open", service: "ssh", version: "OpenSSH" },
      { port: 443, protocol: "tcp", state: "open", service: "https", version: "Generic TLS Service" }
    ],
    last_seen_at: "2026-01-01T12:00:00.000Z",
    device_id: "dev-002",
    first_seen_at: "2026-01-01T12:00:00.000Z",
    open_ports_count: 2,
    highest_severity: "medium"
  },
  {
    ip: "10.0.0.20",
    mac: "AA:BB:CC:DD:EE:03",
    hostname: "device-20.local",
    vendor: "Generic Vendor C",
    ports: [],
    last_seen_at: "2026-01-01T12:00:00.000Z",
    device_id: "dev-003",
    first_seen_at: "2026-01-01T12:00:00.000Z",
    open_ports_count: 0,
    highest_severity: null
  },
  {
    ip: "10.0.0.30",
    mac: "AA:BB:CC:DD:EE:04",
    hostname: "device-30.local",
    vendor: "Generic Vendor D",
    ports: [
      { port: 21, protocol: "tcp", state: "open", service: "ftp", version: "Generic FTP Server" },
      { port: 25, protocol: "tcp", state: "open", service: "smtp", version: "Generic Mail Service" }
    ],
    last_seen_at: "2026-01-01T12:00:00.000Z",
    device_id: "dev-004",
    first_seen_at: "2026-01-01T12:00:00.000Z",
    open_ports_count: 2,
    highest_severity: "high"
  },
  {
    ip: "10.0.0.50",
    mac: "AA:BB:CC:DD:EE:05",
    hostname: "database.local",
    vendor: "Generic Vendor E",
    ports: [
      { port: 3306, protocol: "tcp", state: "open", service: "database", version: "Generic SQL DB" }
    ],
    last_seen_at: "2026-01-01T12:00:00.000Z",
    device_id: "dev-005",
    first_seen_at: "2026-01-01T12:00:00.000Z",
    open_ports_count: 1,
    highest_severity: "medium"
  }
];

export const FINDINGS: Finding[] = [];
