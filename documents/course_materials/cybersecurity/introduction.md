# Introduction to Cybersecurity

## Course Overview

Cybersecurity is the practice of protecting systems, networks, and data from unauthorized access, damage, or disruption. This material introduces the foundational security principle known as the CIA triad: confidentiality, integrity, and availability.

## The CIA Triad

Almost every security concept relates back to one (or more) of these three goals:

- **Confidentiality**: ensuring that information is only accessible to people who are authorized to see it. A confidentiality failure happens when private data — like student records or passwords — is exposed to someone who shouldn't have access.

- **Integrity**: ensuring that data is accurate and hasn't been tampered with, whether by an attacker or by accident. An integrity failure happens when data is modified without authorization, such as an attacker changing a grade in a database.

- **Availability**: ensuring that systems and data are accessible to authorized users when needed. An availability failure happens when a system goes down or becomes unusable, for example due to a denial-of-service attack.

## Why All Three Matter

A secure system needs to protect all three properties, and they sometimes conflict. For example, adding heavy encryption (protecting confidentiality) can slow down a system (affecting availability), so security decisions usually involve tradeoffs based on what matters most for a given system.

## Everyday Examples

- A password-protected file demonstrates **confidentiality**.
- A checksum that detects if a downloaded file was corrupted demonstrates **integrity**.
- A backup server that takes over if the main server fails demonstrates **availability**.

## Looking Ahead

With this foundation, the following materials cover more specific topics: how networks are protected (network security) and common ways attackers try to compromise systems (attack vectors).
