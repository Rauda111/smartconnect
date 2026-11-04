# SmartConnect jury demonstration

From this checkout on the MacBook, run:

```sh
sh /Users/raudaalshaeili/smartconnect/launch_dashboard.command
```

Open http://127.0.0.1:8501. This command opens only a log viewer and does not
start probes, downloads, captures or network changes. Recorded mode works offline.
The launcher uses the existing Anaconda environment on this Mac, or `.venv` when
present. Set SMARTCONNECT_PYTHON to select another environment containing Streamlit,
pandas and Altair. No package installation happens at launch.

## A reproducible 90-second jury tour

1. Keep **Recorded real experiment** selected. Say: “These are eight recorded
   windows from a real File Download experiment, not a live measurement.”
2. Window 1: point out Wi-Fi selection, both ICMP observations, and bounded-object
   calibration goodput. Explain that calibration samples both paths before selection.
3. Window 6: show the selected Wi-Fi HTTPS timeout. The candidate hold is only
   1/3; the goodput comparison has fallen back to RTT/loss after calibration failure.
4. Window 7: Wi-Fi has 0/10 ICMP replies and no RTT. The availability exception
   immediately recommends cellular. The new selected request completes 65,536
   bytes in **224.695 ms**. This is not a completed proactive goodput-based hold.
5. Window 8: cellular completes another 65,536 bytes in **193.062 ms**.
   Run totals are **20/24** completed requests including calibration, **7/8**
   successful selected outcomes. Open the ledger to distinguish the two roles.
6. Say: “Wi-Fi-first makes identical decisions here. This demonstrates integrated
   fallback, not comparative superiority. Socket option readback was confirmed;
   physical egress and existing-session continuity were not packet-confirmed.”
7. Choose **Historical policy replay**, leave Video selected, inspect W4 and W18.
   These replay real ICMP observations through the existing policy; they contain
   no historical HTTPS outcomes or recorded movement-stage boundaries.
8. Choose **Live monitoring** only to read a separately collected, approved JSONL
   log. An absent file gives a safe warning. Return to Recorded mode for the booth.

Optional: toggle Replay animation to loop windows every two seconds. Turn it off
for manual inspection. Restart replay returns animation to W1. Advanced sections
show scoring, margin, hold, dwell, request ledger and evidence limits.

Do not describe this as seamless handover, verified 5G radio, actual video QoE,
packet-confirmed switching, measured handover time or universal Wi-Fi-first gains.
