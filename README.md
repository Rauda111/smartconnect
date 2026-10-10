# SmartConnect

<p align="center">
  <img src="assets/smartconnect_intro.jpg" alt="SmartConnect introductory banner" width="100%">
</p>

## Application-Aware Smart Handover Between Wi-Fi and a 5G-like Network

SmartConnect is a prototype system that improves network handover decisions by selecting the most suitable network based on application needs and network quality conditions. Instead of relying only on signal strength, SmartConnect considers multiple Quality of Service (QoS) metrics such as latency, packet loss, jitter, throughput, and network degradation trends.

The project demonstrates how a user can be moved from Wi-Fi to a 5G-like alternative access network at the right time, depending on the application being used and the observed network conditions.

---

## Problem Statement

Traditional handover approaches often stay connected to Wi-Fi for too long because they depend mainly on signal strength. In real use, this can cause degraded performance for applications such as video calls, where latency, jitter, and packet loss matter more than RSSI alone.

SmartConnect addresses this by making handover decisions using an application-aware and multi-metric decision engine.

---

## Proposed Solution

SmartConnect continuously observes both Wi-Fi and 5G-like network conditions, calculates decision scores based on the active application, detects performance degradation trends, and selects the better network only when the switch is justified.

This helps reduce poor handover timing and improves application experience compared to a strongest-signal-only baseline.

---

## System Architecture

<p align="center">
  <img src="assets/smartconnect_block_diagram.jpg" alt="SmartConnect system architecture block diagram" width="85%">
</p>

The SmartConnect system consists of the following main components:

- **Application Profile Detector** – identifies the type of application in use
- **Metric Collector** – gathers network metrics from available networks
- **Decision Engine** – computes QoS scores, applies application-aware weights, and evaluates trends
- **Handover Controller** – decides whether to remain on the current network or switch
- **Feedback Monitor** – tracks the outcome of decisions and network performance

---

## Key Features

- Strongest-signal baseline for comparison
- SmartConnect application-aware decision engine
- Controlled scenario-based simulation
- Comparison of baseline vs SmartConnect using identical traces
- Streamlit prototype for interactive demonstration
- Cisco Packet Tracer topology to illustrate network connectivity
- Testing and analysis results with plots, tables, and event summaries

---

## Scenarios Tested

The project evaluates behavior under four main scenarios:

1. **Leaving Wi-Fi**
2. **Congested Wi-Fi**
3. **Large Download**
4. **Recovery**

---

## Prototype Demonstration

The Streamlit prototype allows the user to:

- choose a scenario
- choose an application type
- compare baseline vs SmartConnect
- inspect network metrics
- review handover events
- view final results interactively

---

## Repository Structure

```text
smartconnect/
├── analysis/              # Student 3 analysis outputs
├── assets/                # README images
├── cisco/                 # Cisco Packet Tracer topology
├── outputs/               # Simulation CSV outputs
├── plots/                 # Verification plots
├── results/               # Final testing results and tables
├── app.py                 # Streamlit prototype
├── baseline.py            # RSSI-only baseline
├── smartconnect.py        # SmartConnect decision engine
├── simulate.py            # Simulation runner
├── scenarios.py           # Scenario generation
├── config.py              # Shared configuration
├── test_simulation.py     # Simulation tests
├── test_smartconnect.py   # SmartConnect tests
└── README.md
