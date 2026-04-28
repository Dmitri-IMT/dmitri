export type Severity = 'critical' | 'high' | 'medium' | 'low';

export interface Scan {
  scan_id: string;
  timestamp: string;
  subnet: string;
  scan_mode: 'full' | 'quick';
  status: 'completed' | 'accepted' | 'processing' | 'failed';
  device_count: number;
  finding_count: number;
  highest_severity: Severity | null;
  metadata: {
    agent_version: string;
    nmap_arguments: string;
    elapsed_seconds: number;
  };
}

export interface Device {
  device_id: string;
  ip: string;
  mac: string;
  hostname: string;
  vendor: string;
  last_seen_at: string;
  first_seen_at: string;
  open_ports_count: number;
  highest_severity: Severity | null;
  ports: Array<{
    port: number;
    protocol: string;
    state: string;
    service: string;
    version: string;
  }>;
}

export interface Finding {
  finding_id: string;
  scan_id: string;
  device_id: string;
  device_ip: string;
  severity: Severity;
  title: string;
  description: string;
  recommendation: string;
  evidence: string;
  detected_at: string;
}