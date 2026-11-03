# File Download audit and operator decision display

Scope: static inspection and offline mocked integration tests; no new real traffic.
The runner, shared client and Phase4 application policy are unchanged by this
update. Existing movement and smoke evidence is not edited or repackaged.

## Actual data flow

`competition/run.py:live` measures both interfaces with concurrent ICMP windows.
In file_download mode it then calls the existing bound HTTPS client once on each
interface. Both calibration transfers use the same pinned IPv4 endpoint, verified
TLS hostname, /__down?bytes=65536, exact 65,536-byte body limit and five-second
request deadline. Calibration interface order alternates each window. Only after
both complete does `Session.decide` call the preserved Phase4 Controller.
One selected-interface outcome follows the decision; that outcome cannot enter
its own decision. There is no alternate-interface retry or unbound fallback.

Every actual request logs source, role, window, requested interface, socket binding
readback, timestamps, duration, status and body bytes. Each calibration result is
also embedded in the decision event. IP_BOUND_IF is set/read back before connect.
Failures remain failed records; socket readback is not independent physical-egress
proof. Stage4 and new flows remain unverified even when readback/success agree.

Goodput Mbps = completed body bytes * 8 / request_duration_ms / 1000.
The client success must have exact requested length, else runner changes status to
invalid_body_length. Failed, partial, timed-out, nonpositive/nonfinite measurements
produce no goodput. Existing client verifies TLS and limits bodies/timeouts.
Only successful real transfers supply live goodput; mocked transfer results in
unit tests are software checks, never field evidence. Body content is hashed,
not retained for independent content revalidation.

## Meaningful application distinction

Let q_RTT=1-clip((RTT-1)/149,0,1), q_loss=1-clip(loss/5,0,1).
Video Call: Q=0.5*q_RTT+0.5*q_loss. No calibration HTTP is sent for Video Call;
its own selected HTTPS request is a responsiveness proxy, not an actual call.

File Download with both calibration goodputs available:
U=0.8*min(1,G/10 Mbps)+0.2*q_RTT; Q=0.5*U+0.5*q_loss.
Effective weights: 40% capped goodput utility, 10% RTT quality, 50% loss quality.
The utility is mapped into the engine's latency coordinate for reuse; it is not
measured RTT. Dashboard RTT remains the original ICMP input. The 10 Mbps reference
is a fixed heuristic; capacity and the original 20 Mbps throughput guardrail
remain unknown. Legacy original RTT/loss profile-weight coverage is 60% for video,
30% for download; that number is not a full coverage score for the added utility.

If either calibration fails, both paths use the same RTT/loss fallback. Metric-
basis changes reset score histories/pending superiority but retain selected path
and dwell. Both profiles preserve causal five-score trend, .05 margin, three-window
hold, 30-second dwell, and observed-guardrail/availability behavior. Video observed
limits: RTT>60ms or loss>2%; download: loss>3%. There is no RTP jitter measurement.

Offline same-ICMP example: 20 ms RTT and zero loss on both paths; mock calibration
G_wifi=.524288 Mbps and G_cellular=5.24288 Mbps. Video retains Wi-Fi; Download
selects cellular after hold/dwell. Tests independently recompute utility and
raw scores and verify the selected request follows that interface. These numbers
are TEST FIXTURES, not measured field performance.

## Safety, privacy and quality limits

- Calibration order is balanced, not simultaneous or randomized. Endpoint/TLS/
  scheduling effects and load from calibration can influence results.
- Small-object goodput includes full fresh connection/server time; not sustained
  radio capacity. Comparing differently sized experiments is confounded.
- Ten ICMP echoes/window resolve loss in 10 percentage points, too coarse to
  precisely establish 2–3% limits. Zero observed loss is not proof of no loss.
- ICMP and HTTPS endpoints differ; ICMP failure is not a service diagnosis.
  Calibration failure can trigger fallback without establishing interface outage.
- Trends use observation steps, not elapsed-time slope; movement pauses preserve
  history and naturally advance elapsed dwell, not qualifying counts.
- Public display allowlists fields; no local IP/port, raw error, ping text or
  credentials are shown. Private evidence retains tuples needed for later approved
  packet correlation. Keep raw logs local; they are not encrypted by this app.
- Requested selected-interface changes include failed attempts. Successful bound-
  request changes are a different count. Calibration alternation counts as neither.
  Packet-confirmed physical egress and existing-session migration remain unknown.

## Latest real movement experiment: demonstration script

Load the PRIVATE existing live log at
/private/tmp/smartconnect-movement-20261103T205000Z/events.jsonl.
Choose completed decision Windows 3, 4, 5, 6 and 7 in the inspector.
Show raw/adjusted scores, candidate advantage, margin, qualifying count, eligibility
and recorded explanation beside the actual requested outcome interface.

W3/W4: Wi-Fi observed ICMP loss 20%, cellular 0%; cellular adjusted advantages
.677267 and .673522 produce hold 1/3 then 2/3. Dwell already exceeds 30 seconds.
W5: Wi-Fi recovers to zero observed loss; cellular advantage .030560 is below .05,
so the hold resets. W6 qualifies 1/3; W7's improving Wi-Fi trend resets it again.
All eight outcome requests succeeded with en0 socket readback, not packet proof.
This demonstrates rejection of a transient candidate advantage under the frozen
stability rules. Do not assert objectively that switching would have been
"unnecessary" or that the policy improved QoE; remaining on Wi-Fi also exposed
W3's 1350.347ms HTTPS completion. Hysteresis has response-delay costs.

Judge Q: Why did it not switch despite loss?
A: Cellular qualified for only two consecutive windows; Wi-Fi recovered before
   the required third. The paused time satisfied dwell but added no qualifying
   observations. No threshold was changed to manufacture a switch.
Q: How is it application-aware?
A: Video uses RTT/loss; Download additionally uses real equal-size pre-decision
   goodput when available. We can show the calculation and same-input offline
   contrast. This does not establish improved actual video-call QoE.
Q: Does the calibration en0/en6 alternation demonstrate switching?
A: No. It samples both paths deliberately. Only selected-outcome attempts define
   the requested-interface change history; physical egress requires new capture.
