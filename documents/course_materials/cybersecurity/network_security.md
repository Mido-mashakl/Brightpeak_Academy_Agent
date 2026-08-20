# Network Security Basics

## Course Overview

Network security focuses on protecting data as it travels between systems and controlling which traffic is allowed to reach a network in the first place. This material covers firewalls, VPNs, and the basics of securing network traffic.

## Firewalls

A firewall is a system that monitors and controls incoming and outgoing network traffic based on a set of rules. It acts as a barrier between a trusted internal network and untrusted external networks (like the internet).

Firewall rules typically filter traffic based on:

- Source and destination IP address
- Port number (e.g., blocking all traffic except on port 443 for HTTPS)
- Protocol (TCP, UDP, etc.)

For example, a firewall rule might allow traffic on port 443 (HTTPS) but block traffic on port 23 (an outdated, insecure protocol).

## VPNs (Virtual Private Networks)

A VPN creates an encrypted connection ("tunnel") between a user's device and a remote network, so traffic traveling between them can't be read or tampered with by anyone intercepting it along the way.

Common uses for VPNs:

- Allowing remote employees to securely access an internal company network
- Protecting traffic on untrusted networks, like public Wi-Fi
- Masking a user's actual location or IP address

## Encrypting Traffic

Beyond VPNs, individual connections are commonly secured using **TLS** (Transport Layer Security), which is what turns HTTP into HTTPS. TLS encrypts data in transit between a browser and a server, protecting it from being read or modified by anyone in between — even if the underlying network isn't otherwise secured.

## Putting It Together

A well-secured network layers these defenses: firewalls to control what traffic is even allowed in or out, VPNs to secure remote connections, and TLS to encrypt the actual data being exchanged, so that even if traffic is intercepted, it can't be read or altered.
