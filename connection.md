# Laptop B ↔ Laptop K Network Connectivity

## 1. Network Configuration

Both laptops must be connected to the same Airtel Wi-Fi network.

| Device | Role | IPv4 Address |
|---|---|---|
| Laptop B | NIDS server, packet capture and dashboard | `192.168.1.6` |
| Laptop K | Client, browser and traffic generator | `192.168.1.15` |
| Airtel Router | Default gateway | `192.168.1.1` |

Subnet mask: `255.255.255.0`

Both devices belong to the same local subnet: `192.168.1.0/24`.

## 2. Connectivity Requirement

Laptop K must be able to communicate with Laptop B.

The following ping command must succeed when executed on Laptop K:

```powershell
ping 192.168.1.6
```

Expected result:

```text
Reply from 192.168.1.6: bytes=32 time<10ms TTL=...
```

Ping statistics should ideally show:

```text
Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)
```

Laptop B should also be able to ping Laptop K:

```powershell
ping 192.168.1.15
```

Both directions should work for the demonstration's network connectivity verification.

**Important:** Ping uses ICMP. A successful ping confirms ICMP reachability but does not by itself guarantee that the website's TCP port is accessible.

## 3. Windows Firewall Requirements

- Windows Defender Firewall must remain enabled.
- Do not disable the firewall to establish connectivity.
- If ICMP is blocked, configure a temporary inbound ICMPv4 Echo Request rule on Laptop B.
- Restrict the rule's remote address to Laptop K (`192.168.1.15`).
- Apply the rule only to the appropriate trusted network profile.
- Remove the temporary rule after testing.

Example temporary rule (run as Administrator on Laptop B):

```powershell
New-NetFirewallRule `
  -DisplayName "NIDS Demo ICMP Test" `
  -Direction Inbound `
  -Protocol ICMPv4 `
  -IcmpType 8 `
  -RemoteAddress 192.168.1.15 `
  -Action Allow `
  -Profile Private
```

Cleanup:

```powershell
Remove-NetFirewallRule -DisplayName "NIDS Demo ICMP Test"
```

## 4. Network Profile

Use the Public profile by default.

Only switch Laptop B's Wi-Fi to Private temporarily if the network is trusted and the demonstration requires it.

Check the current profile:

```powershell
Get-NetConnectionProfile
```

## 5. Additional Connectivity Verification

After starting the demonstration website on Laptop B, verify TCP connectivity from Laptop K:

```powershell
Test-NetConnection -ComputerName 192.168.1.6 -Port 8080
```

Expected:

```text
TcpTestSucceeded : True
```

Then open the website on Laptop K:

```text
http://192.168.1.6:8080
```

## 6. Security Restrictions

- Do not disable Windows Firewall.
- Do not open all inbound ports.
- Do not expose FastAPI or PostgreSQL unnecessarily.
- Restrict website access to Laptop K's IP where practical.
- Do not change Airtel router isolation settings without authorization.
- Remove temporary firewall rules after the demonstration.
- Restore the original network profile after testing if it was changed.

## 7. Final Acceptance Criteria

The network setup is considered ready when:

- [ ] Both laptops are connected to the same Wi-Fi.
- [ ] Both have valid IPv4 addresses in the expected subnet.
- [ ] Laptop K can ping Laptop B.
- [ ] Laptop B can ping Laptop K.
- [ ] Laptop K can establish a TCP connection to port 8080.
- [ ] Laptop K can open the demonstration website.
- [ ] Windows Firewall remains enabled.