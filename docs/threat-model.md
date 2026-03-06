# Initial Threat Model

## Assets
- **Scan data**: Raw and normalized findings describing devices, ports, and vulnerabilities.
- **Credentials**: API tokens used by the hardware agent and mobile app.
- **Hardware device**: Physical Raspberry Pi deployed on customer networks.
- **Backend infrastructure**: API servers, PostgreSQL database, and CI pipelines.

## Adversaries & Motivations
- Network attackers attempting to intercept or alter scan data.
- Malicious insiders trying to tamper with reports or delete evidence.
- Unauthorized devices impersonating the legitimate agent.

## Attack Surfaces
1. **Device Communication**
   - Mitigation: Enforce HTTPS/TLS 1.2+, pin backend certificates on the agent, rotate credentials.
2. **Backend API**
   - Mitigation: Apply authentication + authorization middleware, rate limiting, and payload validation.
3. **Data Storage**
   - Mitigation: Encrypt PostgreSQL at rest, limit access via roles, implement audit logging.
4. **Supply Chain**
   - Mitigation: Sign container images, lock dependencies, and scan artifacts in CI.
5. **Physical Device**
   - Mitigation: Disable unused services, enforce secure boot configurations, and protect SD cards with filesystem encryption when possible.

## Trust Boundaries
- Between the hardware agent and backend over the public/private network.
- Between backend microservices and the PostgreSQL database within the Docker network.
- Between CI workflows and production infrastructure.

## Next Steps
- Complete STRIDE analysis per component.
- Define incident response playbooks for compromised agents.
- Add sequence diagrams showing authentication and data processing steps.
