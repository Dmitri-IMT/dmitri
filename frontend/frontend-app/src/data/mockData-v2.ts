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
    scan_id: "cd082aec-e0fb-4190-9f45-9f34c443ce94",
    timestamp: "2026-06-10T22:05:32.437225Z",
    subnet: "192.168.56.0/24",
    scan_mode: "full",
    status: "completed",
    device_count: 3,
    finding_count: 301,
    highest_severity: "critical",
    metadata: {
      agent_version: "0.1.3",
      nmap_arguments: "discovery=-sn -PE -T4; ports=-sV -O --top-ports 10000 -Pn -T4; deep_inspection=-sV --version-intensity 5; scripts=vulners,smb-protocols,smb2-security-mode,ssh-auth-methods,http-title,http-server-header,ssl-cert,ssl-enum-ciphers,http-methods,ftp-anon,banner; min_cvss=3.0; workers=4; host_batch_size=8",
      elapsed_seconds: 362.96
    }
  }
];

export const DEVICES: Device[] = [
  {
    device_id: "dev-192-168-56-100",
    ip: "192.168.56.100",
    mac: "08:00:27:20:51:70",
    hostname: "192.168.56.100",
    vendor: "Oracle VirtualBox virtual NIC",
    first_seen_at: "2026-06-10T22:05:32.437225Z",
    last_seen_at: "2026-06-10T22:05:32.437225Z",
    open_ports_count: 0,
    highest_severity: null,
    ports: []
  },
  {
    device_id: "dev-192-168-56-101",
    ip: "192.168.56.101",
    mac: "08:00:27:BA:E1:D4",
    hostname: "192.168.56.101",
    vendor: "Oracle VirtualBox virtual NIC",
    first_seen_at: "2026-06-10T22:05:32.437225Z",
    last_seen_at: "2026-06-10T22:05:32.437225Z",
    open_ports_count: 26,
    highest_severity: "critical",
    ports: [
      { port: 21,   protocol: "tcp", state: "open", service: "ftp",         version: "vsftpd 2.3.4" },
      { port: 22,   protocol: "tcp", state: "open", service: "ssh",         version: "OpenSSH 4.7p1 Debian 8ubuntu1 protocol 2.0" },
      { port: 23,   protocol: "tcp", state: "open", service: "telnet",      version: "Linux telnetd" },
      { port: 25,   protocol: "tcp", state: "open", service: "smtp",        version: "Postfix smtpd" },
      { port: 53,   protocol: "tcp", state: "open", service: "domain",      version: "ISC BIND 9.4.2" },
      { port: 80,   protocol: "tcp", state: "open", service: "http",        version: "Apache httpd 2.2.8 (Ubuntu) DAV/2" },
      { port: 111,  protocol: "tcp", state: "open", service: "rpcbind",     version: "" },
      { port: 139,  protocol: "tcp", state: "open", service: "netbios-ssn", version: "Samba smbd 3.X - 4.X workgroup: WORKGROUP" },
      { port: 445,  protocol: "tcp", state: "open", service: "netbios-ssn", version: "Samba smbd 3.X - 4.X workgroup: WORKGROUP" },
      { port: 512,  protocol: "tcp", state: "open", service: "exec",        version: "netkit-rsh rexecd" },
      { port: 513,  protocol: "tcp", state: "open", service: "login",       version: "" },
      { port: 514,  protocol: "tcp", state: "open", service: "shell",       version: "Netkit rshd" },
      { port: 1099, protocol: "tcp", state: "open", service: "java-rmi",    version: "GNU Classpath grmiregistry" },
      { port: 1524, protocol: "tcp", state: "open", service: "bindshell",   version: "Metasploitable root shell" },
      { port: 2049, protocol: "tcp", state: "open", service: "rpcbind",     version: "" },
      { port: 2121, protocol: "tcp", state: "open", service: "ftp",         version: "ProFTPD 1.3.1" },
      { port: 3306, protocol: "tcp", state: "open", service: "mysql",       version: "MySQL 5.0.51a-3ubuntu5" },
      { port: 3632, protocol: "tcp", state: "open", service: "distccd",     version: "distccd v1 (GNU) 4.2.4 (Ubuntu 4.2.4-1ubuntu4)" },
      { port: 5432, protocol: "tcp", state: "open", service: "postgresql",  version: "PostgreSQL DB 8.3.0 - 8.3.7" },
      { port: 5900, protocol: "tcp", state: "open", service: "vnc",         version: "VNC protocol 3.3" },
      { port: 6000, protocol: "tcp", state: "open", service: "X11",         version: "access denied" },
      { port: 6667, protocol: "tcp", state: "open", service: "irc",         version: "UnrealIRCd" },
      { port: 6697, protocol: "tcp", state: "open", service: "irc",         version: "UnrealIRCd" },
      { port: 8009, protocol: "tcp", state: "open", service: "ajp13",       version: "Apache Jserv Protocol v1.3" },
      { port: 8180, protocol: "tcp", state: "open", service: "http",        version: "Apache Tomcat/Coyote JSP engine 1.1" },
      { port: 8787, protocol: "tcp", state: "open", service: "drb",         version: "Ruby DRb RMI Ruby 1.8; path /usr/lib/ruby/1.8/drb" }
    ]
  },
  {
    device_id: "dev-192-168-56-1",
    ip: "192.168.56.1",
    mac: "",
    hostname: "192.168.56.1",
    vendor: "unknown",
    first_seen_at: "2026-06-10T22:05:32.437225Z",
    last_seen_at: "2026-06-10T22:05:32.437225Z",
    open_ports_count: 8,
    highest_severity: null,
    ports: [
      { port: 135,  protocol: "tcp", state: "open",     service: "msrpc",       version: "Microsoft Windows RPC" },
      { port: 137,  protocol: "tcp", state: "filtered", service: "netbios-ns",  version: "" },
      { port: 139,  protocol: "tcp", state: "open",     service: "netbios-ssn", version: "Microsoft Windows netbios-ssn" },
      { port: 445,  protocol: "tcp", state: "open",     service: "microsoft-ds",version: "" },
      { port: 808,  protocol: "tcp", state: "open",     service: "mc-nmf",      version: ".NET Message Framing" },
      { port: 2968, protocol: "tcp", state: "open",     service: "enpp",        version: "" },
      { port: 5040, protocol: "tcp", state: "open",     service: "tcpwrapped",  version: "" },
      { port: 5432, protocol: "tcp", state: "open",     service: "postgresql",  version: "PostgreSQL DB Portuguese" },
      { port: 6881, protocol: "tcp", state: "open",     service: "tcpwrapped",  version: "" }
    ]
  }
];

// Helper para gerar IDs de findings sequenciais
const mkFinding = (() => {
  let n = 0;
  return (
    scanId: string,
    deviceId: string,
    deviceIp: string,
    severity: Severity,
    title: string,
    description: string,
    recommendation: string,
    evidence: string,
    detectedAt: string
  ): Finding => ({
    finding_id: `finding-${String(++n).padStart(4, '0')}`,
    scan_id: scanId,
    device_id: deviceId,
    device_ip: deviceIp,
    severity,
    title,
    description,
    recommendation,
    evidence,
    detected_at: detectedAt
  });
})();

const SCAN_ID   = "cd082aec-e0fb-4190-9f45-9f34c443ce94";
const DEV_101   = "dev-192-168-56-101";
const IP_101    = "192.168.56.101";
const TS        = "2026-06-10T22:05:32.437225Z";

export const FINDINGS: Finding[] = [
  // ── FTP / vsftpd 2.3.4 ──────────────────────────────────────────────────
  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2011-2523: vsftpd 2.3.4 backdoor",
    "O serviço vsftpd 2.3.4 (TCP/21) possui uma backdoor conhecida (CVE-2011-2523) que permite execução remota de comandos.",
    "Atualize o vsftpd para a versão mais recente e restrinja o acesso ao serviço FTP.",
    "vulners matched vsftpd 2.3.4 (TCP/21) to CVE-2011-2523", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "high",
    "Login FTP anônimo permitido",
    "O serviço FTP em 192.168.56.101:21 permite login anônimo, podendo expor arquivos a usuários não autenticados.",
    "Desabilite o acesso FTP anônimo ou restrinja-o a um diretório controlado somente leitura.",
    "Anonymous FTP login allowed (FTP code 230)", TS),

  // ── SSH / OpenSSH 4.7p1 ──────────────────────────────────────────────────
  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2023-38408: RCE remoto no ssh-agent (OpenSSH 4.7p1)",
    "O serviço OpenSSH 4.7p1 está vinculado ao CVE-2023-38408, que permite execução remota de código via ssh-agent.",
    "Atualize o OpenSSH para a versão mais recente e desative o encaminhamento do agente SSH quando não necessário.",
    "vulners matched OpenSSH 4.7p1 to CVE-2023-38408", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2016-1908: Fallback de credenciais inseguro no OpenSSH",
    "O OpenSSH 4.7p1 está sujeito ao CVE-2016-1908, permitindo bypass de controle de acesso.",
    "Atualize o OpenSSH para a versão mais recente e aplique o patch do fornecedor.",
    "vulners matched OpenSSH 4.7p1 to CVE-2016-1908", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2010-4478: Bypass de autenticação no OpenSSH",
    "O OpenSSH 4.7p1 está sujeito ao CVE-2010-4478 (CVSS 9.8), que pode permitir bypass de autenticação.",
    "Atualize o OpenSSH imediatamente para uma versão suportada.",
    "vulners matched OpenSSH 4.7p1 to CVE-2010-4478", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "high",
    "CVE-2015-5600: Bypass de limite de tentativas no OpenSSH",
    "O OpenSSH 4.7p1 permite contornar o limite de tentativas de autenticação por teclado (CVE-2015-5600, CVSS 8.5).",
    "Atualize o OpenSSH e configure MaxAuthTries adequadamente.",
    "vulners matched OpenSSH 4.7p1 to CVE-2015-5600", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "high",
    "CVE-2020-15778: Injeção de comandos via scp no OpenSSH",
    "O OpenSSH 4.7p1 é vulnerável à injeção de comandos via scp (CVE-2020-15778, CVSS 7.8).",
    "Atualize o OpenSSH e evite o uso do scp legado; prefira sftp ou rsync.",
    "vulners matched OpenSSH 4.7p1 to CVE-2020-15778", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "high",
    "CVE-2016-6515: DoS por senha longa no OpenSSH",
    "O OpenSSH 4.7p1 aceita senhas de comprimento arbitrário, possibilitando DoS (CVE-2016-6515, CVSS 7.8).",
    "Atualize o OpenSSH para a versão mais recente.",
    "vulners matched OpenSSH 4.7p1 to CVE-2016-6515", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "low",
    "Autenticação SSH por senha exposta",
    "O serviço SSH em 192.168.56.101:22 permite autenticação por senha, aumentando exposição a força bruta.",
    "Prefira autenticação por chave SSH; restrinja acesso à rede e monitore tentativas de login.",
    "Supported authentication methods: publickey, password", TS),

  // ── DNS / ISC BIND 9.4.2 ─────────────────────────────────────────────────
  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2008-0122: Estouro de buffer no ISC BIND 9.4.2",
    "O ISC BIND 9.4.2 está sujeito ao CVE-2008-0122 (CVSS 10.0), permitindo execução remota de código.",
    "Atualize o BIND para uma versão suportada e restrinja consultas DNS recursivas.",
    "vulners matched ISC BIND 9.4.2 to CVE-2008-0122", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2021-25216: Estouro de buffer TKEY no BIND 9.4.2",
    "O ISC BIND 9.4.2 é vulnerável ao CVE-2021-25216 (CVSS 9.8), causando crash ou execução de código via TKEY.",
    "Atualize o BIND imediatamente para uma versão suportada.",
    "vulners matched ISC BIND 9.4.2 to CVE-2021-25216", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "high",
    "CVE-2020-8616: Amplificação NXNS no BIND 9.4.2",
    "O BIND 9.4.2 permite ataques de amplificação DNS via delegações NXNS (CVE-2020-8616, CVSS 8.6).",
    "Atualize o BIND e limite o número de referências de NS por consulta.",
    "vulners matched ISC BIND 9.4.2 to CVE-2020-8616", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "high",
    "CVE-2016-1286: DoS de assertion no BIND 9.4.2",
    "O BIND 9.4.2 é vulnerável ao CVE-2016-1286 (CVSS 8.6), podendo causar falha de assertion e crash do named.",
    "Atualize o BIND para uma versão suportada.",
    "vulners matched ISC BIND 9.4.2 to CVE-2016-1286", TS),

  // ── HTTP / Apache 2.2.8 ──────────────────────────────────────────────────
  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2010-0425: Execução remota de código no Apache 2.2.8",
    "O Apache httpd 2.2.8 está sujeito ao CVE-2010-0425 (CVSS 10.0), permitindo execução remota de código.",
    "Atualize o Apache para uma versão suportada e aplique as correções do fornecedor.",
    "vulners matched Apache httpd 2.2.8 to CVE-2010-0425", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2022-31813: Bypass de controle de acesso no Apache 2.2.8",
    "O Apache httpd 2.2.8 é vulnerável ao CVE-2022-31813 (CVSS 9.8), permitindo bypass de autenticação.",
    "Atualize o Apache para a versão mais recente.",
    "vulners matched Apache httpd 2.2.8 to CVE-2022-31813", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2021-44790: Estouro de buffer no mod_lua do Apache 2.2.8",
    "O Apache httpd 2.2.8 é vulnerável ao CVE-2021-44790 (CVSS 9.8) no módulo mod_lua.",
    "Atualize o Apache e desabilite módulos não utilizados.",
    "vulners matched Apache httpd 2.2.8 to CVE-2021-44790", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2017-7679: Estouro de buffer no mod_mime do Apache 2.2.8",
    "O Apache httpd 2.2.8 é vulnerável ao CVE-2017-7679 (CVSS 9.8) no módulo mod_mime.",
    "Atualize o Apache para a versão mais recente.",
    "vulners matched Apache httpd 2.2.8 to CVE-2017-7679", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2009-3555: Renegociação TLS insegura no Apache 2.2.8",
    "O Apache httpd 2.2.8 é vulnerável ao CVE-2009-3555 (CVSS 9.8), permitindo ataques man-in-the-middle via renegociação TLS.",
    "Atualize o Apache e o OpenSSL; desabilite renegociação TLS insegura.",
    "vulners matched Apache httpd 2.2.8 to CVE-2009-3555", TS),

  // ── SMTP / TLS fraco ──────────────────────────────────────────────────────
  mkFinding(SCAN_ID, DEV_101, IP_101, "medium",
    "Protocolo SSLv3 obsoleto habilitado (SMTP :25)",
    "O serviço SMTP em 192.168.56.101:25 oferece SSLv3, um protocolo obsoleto e vulnerável ao POODLE.",
    "Desabilite SSLv3 e TLSv1.0; exija TLS 1.2 ou superior.",
    "SSLv3 detectado com cifras com grau F, incluindo CBC-mode cipher (CVE-2014-3566)", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "medium",
    "Cifras TLS fracas no SMTP :25 (grau F)",
    "O SMTP em 192.168.56.101:25 oferece cifras com grau F, incluindo RC4, 3DES e troca de chaves anônima.",
    "Remova cifras de baixo grau; prefira suítes AEAD modernas.",
    "Cifras mais fracas incluem RC4 depreciado (RFC 7465), 3DES vulnerável ao SWEET32 e troca de chaves anônima", TS),

  // ── ProFTPD 1.3.1 ────────────────────────────────────────────────────────
  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2019-12815: Cópia arbitrária de arquivos no ProFTPD 1.3.1",
    "O ProFTPD 1.3.1 é vulnerável ao CVE-2019-12815 (CVSS 9.8), permitindo cópia arbitrária de arquivos sem autenticação.",
    "Atualize o ProFTPD para a versão mais recente.",
    "vulners matched ProFTPD 1.3.1 to CVE-2019-12815", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2011-4130: Uso após liberação no ProFTPD 1.3.1",
    "O ProFTPD 1.3.1 é vulnerável ao CVE-2011-4130 (CVSS 9.0), um bug use-after-free com potencial de execução remota.",
    "Atualize o ProFTPD imediatamente.",
    "vulners matched ProFTPD 1.3.1 to CVE-2011-4130", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "high",
    "CVE-2024-48651: Vulnerabilidade no ProFTPD 1.3.1",
    "O ProFTPD 1.3.1 está vinculado ao CVE-2024-48651 (CVSS 7.5).",
    "Atualize o ProFTPD para a versão mais recente.",
    "vulners matched ProFTPD 1.3.1 to CVE-2024-48651", TS),

  // ── MySQL 5.0.51a ────────────────────────────────────────────────────────
  mkFinding(SCAN_ID, DEV_101, IP_101, "high",
    "CVE-2017-15945: Escalonamento de privilégios no MySQL 5.0.51a",
    "O MySQL 5.0.51a é vulnerável ao CVE-2017-15945 (CVSS 7.8), permitindo escalonamento de privilégios local.",
    "Atualize o MySQL para uma versão suportada e restrinja o acesso à porta 3306.",
    "vulners matched MySQL 5.0.51a to CVE-2017-15945", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "medium",
    "CVE-2009-4028: Bypass de verificação SSL no MySQL 5.0.51a",
    "O MySQL 5.0.51a é vulnerável ao CVE-2009-4028 (CVSS 6.8), permitindo bypass da verificação de certificado SSL.",
    "Atualize o MySQL e configure SSL corretamente.",
    "vulners matched MySQL 5.0.51a to CVE-2009-4028", TS),

  // ── PostgreSQL 8.3 ───────────────────────────────────────────────────────
  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2013-1903: Execução de código como superusuário no PostgreSQL 8.3",
    "O PostgreSQL 8.3 é vulnerável ao CVE-2013-1903 (CVSS 10.0), permitindo execução de código como superusuário.",
    "Atualize o PostgreSQL para uma versão suportada imediatamente.",
    "vulners matched PostgreSQL 8.3 to CVE-2013-1903", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2013-1902: Execução de processos arbitrários no PostgreSQL 8.3",
    "O PostgreSQL 8.3 é vulnerável ao CVE-2013-1902 (CVSS 10.0), permitindo execução de processos arbitrários.",
    "Atualize o PostgreSQL imediatamente.",
    "vulners matched PostgreSQL 8.3 to CVE-2013-1902", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2019-10211: Estouro de buffer no PostgreSQL 8.3",
    "O PostgreSQL 8.3 é vulnerável ao CVE-2019-10211 (CVSS 9.8), com potencial de execução remota de código.",
    "Atualize o PostgreSQL para a versão mais recente.",
    "vulners matched PostgreSQL 8.3 to CVE-2019-10211", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "CVE-2016-7048: Instalador inseguro do PostgreSQL 8.3",
    "O PostgreSQL 8.3 está vinculado ao CVE-2016-7048 (CVSS 9.3), relacionado ao instalador inseguro.",
    "Atualize o PostgreSQL e revise as permissões de instalação.",
    "vulners matched PostgreSQL 8.3 to CVE-2016-7048", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "medium",
    "Protocolo SSLv3 obsoleto habilitado (PostgreSQL :5432)",
    "O PostgreSQL em 192.168.56.101:5432 oferece SSLv3, um protocolo obsoleto e vulnerável ao POODLE.",
    "Desabilite SSLv3 e TLSv1.0 no postgresql.conf; exija TLS 1.2 ou superior.",
    "SSLv3 detectado com cifras com grau F, incluindo RC4 e 3DES (CVE-2014-3566)", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "medium",
    "Cifras TLS fracas no PostgreSQL :5432 (grau F)",
    "O PostgreSQL em 192.168.56.101:5432 oferece cifras com grau F, incluindo RC4 e 3DES.",
    "Configure ssl_ciphers no postgresql.conf para aceitar apenas suítes AEAD modernas.",
    "Cifras mais fracas incluem RC4 depreciado (RFC 7465) e 3DES vulnerável ao SWEET32", TS),

  // ── Serviços perigosos expostos ──────────────────────────────────────────
  mkFinding(SCAN_ID, DEV_101, IP_101, "critical",
    "Backdoor shell root exposta na porta 1524 (bindshell)",
    "O serviço identificado como 'Metasploitable root shell' está ativo na porta 1524, fornecendo acesso root sem autenticação.",
    "Encerre o processo imediatamente, isole o host e realize análise forense.",
    "Port 1524/tcp open bindshell: Metasploitable root shell", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "high",
    "Telnet (porta 23) exposto sem criptografia",
    "O serviço Telnet está ativo em 192.168.56.101:23, transmitindo dados (incluindo credenciais) em texto claro.",
    "Desabilite o Telnet e substitua por SSH para acesso remoto seguro.",
    "Port 23/tcp open telnet Linux telnetd", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "high",
    "Serviços rsh/rexec legados expostos (portas 512-514)",
    "Os serviços rexec (512), rlogin (513) e rsh (514) estão ativos, transmitindo dados em texto claro sem autenticação forte.",
    "Desabilite os serviços r* e utilize SSH como substituto seguro.",
    "Ports 512/tcp (rexecd), 513/tcp (login), 514/tcp (rshd) open", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "high",
    "VNC exposto sem criptografia (porta 5900)",
    "O serviço VNC 3.3 está ativo em 192.168.56.101:5900 com protocolo que não oferece criptografia nativa.",
    "Configure VNC com autenticação forte e tunelamento via SSH, ou substitua por uma solução de acesso remoto segura.",
    "Port 5900/tcp open VNC protocol 3.3", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "high",
    "UnrealIRCd exposto (portas 6667/6697)",
    "O servidor IRC UnrealIRCd está ativo. Versões antigas do UnrealIRCd possuem backdoors conhecidas.",
    "Verifique a versão do UnrealIRCd, remova o serviço se não for necessário e aplique patches.",
    "Ports 6667/tcp e 6697/tcp open irc UnrealIRCd", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "medium",
    "distccd exposto (porta 3632)",
    "O daemon de compilação distribuída distccd está ativo em 192.168.56.101:3632, podendo ser explorado para execução remota de comandos.",
    "Restrinja o acesso ao distccd via firewall ou desabilite o serviço se não for necessário.",
    "Port 3632/tcp open distccd v1 (GNU) 4.2.4", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "medium",
    "Ruby DRb RMI exposto (porta 8787)",
    "O serviço Ruby DRb (Distributed Ruby) está ativo em 192.168.56.101:8787, podendo permitir execução remota de objetos Ruby.",
    "Restrinja o acesso ao DRb via firewall ou desabilite o serviço se não for necessário.",
    "Port 8787/tcp open drb Ruby DRb RMI Ruby 1.8", TS),

  mkFinding(SCAN_ID, DEV_101, IP_101, "medium",
    "Java RMI Registry exposto (porta 1099)",
    "O serviço Java RMI Registry está ativo em 192.168.56.101:1099, podendo ser explorado para execução remota de código.",
    "Restrinja o acesso à porta 1099 via firewall. Considere desabilitar se não for utilizado.",
    "Port 1099/tcp open java-rmi GNU Classpath grmiregistry", TS),
];