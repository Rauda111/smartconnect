# Two-minute SmartConnect jury walkthrough

Launch on the MacBook from the finalized local branch:

```sh
sh /Users/raudaalshaeili/smartconnect/launch_dashboard.command
```

Open http://127.0.0.1:8501. The existing launcher selects `.venv` when present,
otherwise this Mac's Anaconda Python. Set `SMARTCONNECT_PYTHON` to use another
installed environment with Streamlit, pandas and Altair. It installs nothing and
starts only a localhost viewer. Recorded playback works offline.

## The two-minute tour

**0:00–0:20 · Monitor.** Keep Recorded real experiment selected. Say: “These are
real saved results from November 4, UAE time, not live measurements.” Point to
both connection cards. Response time is the ICMP round trip; missed replies are
ICMP loss. The small-download measurement is bounded HTTPS goodput, not capacity.

**0:20–0:40 · Decide.** Click W6. Wi-Fi remained selected while cellular had only
one qualifying observation out of the normal three-window hold. Show the failed
Wi-Fi request. Explain: “The normal hold and wait reduce flip-flopping.”

**0:40–1:05 · Act.** Click W7, or focus its timeline button with Tab and press
Enter. “Wi-Fi returned zero replies out of ten. The availability exception chose
cellular immediately. This was not a proactive goodput-driven switch.” Point to
the new HTTPS request: 64 KiB completed in **224.695 ms**. Click Next: W8 completed
another 64 KiB in **193.062 ms**. No existing session was migrated.

**1:05–1:25 · Verify.** Show the Completed result and socket-setting readback.
“Readback confirms the requested socket option; physical egress was not packet
confirmed.” The whole run completed **20/24** HTTPS requests including calibration;
**7/8** selected outcomes succeeded. Wi-Fi-first made identical selections here,
so this demonstrates integrated fallback rather than comparative superiority.

**1:25–1:45 · Interact.** Restart, choose a speed, Play, then Pause or select a
window. Native buttons support keyboard activation. The final window says
Finished and stays there; Restart returns to W1. Opening Technical Details pauses
and locks playback. Explain terms opens the glossary. Back to Overview leaves
replay paused. Optional Guided demo tour describes Monitor → Decide → Act → Verify.

**1:45–2:00 · Distinguish the evidence.** Briefly select Historical policy replay:
18 real ICMP windows, replayed policy decisions, no historical HTTPS outcomes or
recorded movement boundaries. Select Live monitoring to show its helpful empty
state or read an existing approved log. This screen never starts a collector.
Return to Recorded real experiment for the next visitor.

## Operator notes

- Timeline clicks, Previous/Next, speed changes, tour changes and mode changes
  pause replay. Technical inspection cannot resume it automatically.
- In Live monitoring, choose the known approved location when available, or enter
  an existing log path in the masked field. Refresh log only re-reads files. No
  private path or raw error is printed in the public overview/status messages.
- Live files without a completion manifest are labelled Incomplete run; this does
  not certify an active collector. Missing, stale, corrupt and finished states
  are distinguished. Inspecting old windows never jumps to the newest silently.
- No verified 5G radio, actual video QoE, universal improvement, seamless handover,
  measured handover time or packet-confirmed physical switching is claimed.
