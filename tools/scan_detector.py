from collections import defaultdict
from scapy.all import PcapReader, IP, TCP


class PortScanDetector:

    def __init__(self, window_seconds=30, min_ports=5):
        self.window_seconds = window_seconds
        self.min_ports = min_ports
        self.attempts = defaultdict(dict)
        self.last_alert = {}

    def process_pcap(self, pcap_path):
        alerts = []

        with PcapReader(str(pcap_path)) as packets:
            for packet in packets:
                if IP not in packet or TCP not in packet:
                    continue

                ip = packet[IP]
                tcp = packet[TCP]
                flags = int(tcp.flags)
                timestamp = float(packet.time)

                # Remove expired observations.
                for key, ports in list(self.attempts.items()):
                    for port, seen in list(ports.items()):
                        if timestamp - seen > self.window_seconds:
                            del ports[port]

                    if not ports:
                        del self.attempts[key]

                for key, seen in list(self.last_alert.items()):
                    if timestamp - seen >= self.window_seconds:
                        del self.last_alert[key]

                # Initial SYN without ACK.
                if not (flags & 0x02) or (flags & 0x10):
                    continue

                key = (ip.src, ip.dst)
                ports = self.attempts[key]
                ports[int(tcp.dport)] = timestamp

                if len(ports) < self.min_ports:
                    continue

                if key in self.last_alert:
                    continue

                alerts.append({
                    "type": "Suspected Port Scan",
                    "source_ip": ip.src,
                    "destination_ip": ip.dst,
                    "distinct_ports": len(ports),
                    "destination_ports": sorted(ports),
                    "window_seconds": self.window_seconds,
                    "timestamp": timestamp,
                    "detection_method": "behavioral"
                })

                self.last_alert[key] = timestamp

        return alerts


def detect_port_scans(
    pcap_path,
    window_seconds=30,
    min_ports=5
):
    detector = PortScanDetector(
        window_seconds=window_seconds,
        min_ports=min_ports
    )

    return detector.process_pcap(pcap_path)
