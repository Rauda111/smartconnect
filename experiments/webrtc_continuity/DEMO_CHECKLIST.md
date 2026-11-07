# Competition demonstration · 9–13 November 2026

## Before the session

- [ ] Keep the existing Prototype 1 dashboard and recorded evidence available.
- [ ] Verify the approved deployed revision matches this integration; do not assume the unchanged current Render deployment includes it.
- [ ] Confirm a separate private writer token, shared signaling access and one broker process/instance.
- [ ] Confirm Mac `en0` and current iPhone USB interface, Windows connectivity, headphones, media permissions and moving video/audio.
- [ ] Approve the exact media/signaling/ICE/TURN destinations, ICMP target, cellular use and duration. Approve perturbation and capture separately at their stages.
- [ ] Use identical baseline/assisted settings and approved ICE configuration on both peers. Check TURN credential expiry privately if used.

## Explain what Prototype 2 adds

“Prototype 1 recommends a network from measured quality. Prototype 2 connects that same decision engine to a real video call. It requests recovery while retaining the call, records media progress and interruption, and separates the recommended network from the path we can independently verify.”

Do not repeat the full scoring presentation here. Show the new integration chain:

1. Real Mac RTT/loss; derived score/trend; unavailable metrics clearly labeled.
2. Existing engine recommendation and its original stay/switch explanation.
3. Requested recovery cause, attempt and ICE state.
4. Actual media counters and interruption intervals.
5. Observed selected pair and the separate physical verification status.

## During an approved trial

- [ ] Start B and A in the same condition; enable policy-driven recovery on Mac A only for the assisted trial.
- [ ] Start the approved bridge with a fresh journal filename and bounded duration.
- [ ] Confirm increasing media counters on both peers and fresh policy input before perturbation.
- [ ] Collect private pre-transition path evidence; independently establish cellular feasibility.
- [ ] Apply only the explicitly approved perturbation; retain every failed attempt.
- [ ] Continue one call without reload or camera reacquisition. Record media recovery or failure and independently check the post-transition path.
- [ ] Download sanitized observations on both peers, stop the bridge and explicitly end the call.

## If the trial does not recover

Show the actual failure, unavailable measurements, exhausted retries or unverified path. End explicitly. The stable Prototype 1 demonstration remains available. A separately started cellular call is a new-session feasibility result and must not be presented as a successful handover.

Use [HARDWARE_VALIDATION.md](HARDWARE_VALIDATION.md) for the full experiment and trial record. The implemented software and offline tests do not by themselves establish same-session physical migration or seamlessness.
