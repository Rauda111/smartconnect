# Controlled-call feasibility assessment — 6 November 2026

Decision: **viable as an isolated WebRTC recovery research prototype; not yet a
verified Wi-Fi → cellular continuity demonstration, and not ready as an EDGE
claim.** No call, DNS experiment, probe, capture or system change was run here.

## Inspected environment and existing implementation

Base: d273c2d14afe474637fc9dc8b5794381560b100a on codex/dashboard-finalization.
The existing HTTPS client creates a fresh IPv4 socket, applies Darwin IP_BOUND_IF
(25), checks readback, then starts TCP/TLS. This cannot retarget a browser-owned
UDP/DTLS/SRTP transport, nor migrate another application's established session.
The installed SDK declares IP_BOUND_IF=25 and IPV6_BOUND_IF=125. Those options are
usable on sockets the program owns, not exposed by JavaScript WebRTC.

Read-only inventory: macOS 15.5; Chrome 157.0.8103.39; Node v24.13.0 at
/usr/local/bin/node; Anaconda Python 3.13.5 reports x86_64 (possibly translation on
the user-reported M1; physical CPU was not independently verified). aiohttp 3.11.10,
Flask 3.1.0 and cryptography 44.0.1 are installed. aiortc, aioice and av are absent;
websockets, Starlette and uvicorn are absent in that Python environment. No
packages were installed. Browser WebRTC plus Python's standard library avoids
changing the frozen environment. Installed browser APIs/permissions still require
an approved live check; dependency presence is not a successful call.

## What can work without system changes

Two controlled browser clients use camera/microphone tracks and actual WebRTC
DTLS/SRTP. An ICE restart is negotiated on the **same RTCPeerConnection**, preserving
its senders and local tracks; this is recovery within an application session,
not a new call hidden behind the UI. ICE restart needs a new offer/answer exchange;
calling restartIce alone does not complete recovery. Browser/remote connectivity
and media continuity during renegotiation remain empirical questions.
[WebRTC specification](https://www.w3.org/TR/webrtc/)

The existing, unchanged Video policy's completed recommendations can be read from
an explicitly selected collector file. A fresh change may request ICE restart.
It cannot compel the browser to choose en0/en6: the standard RTCConfiguration
controls ICE servers and candidate policy, not named OS interfaces. SDP filtering
and navigator.connection are not substitutes for socket binding. Both the policy
recommendation and the unknown actual interface must remain visible. A browser
may recover on its own; an ordinary-WebRTC baseline is therefore necessary.
[RTCConfiguration and ICE](https://www.w3.org/TR/webrtc/)

## Signaling and peer connectivity

The included loopback broker automates signaling for two tabs on this Mac only.
That is a genuine media smoke test, **not a cellular-path test**: ICE may choose
loopback or local host candidates. For controlled clients on different machines,
manual full-SDP exchange is supported with independently served local pages. That
exchange contains private ICE addresses/credentials: use a private approved
channel, never the public dashboard or committed evidence. Manual exchange is
functional but cannot establish automatic/seamless recovery. A resilient,
authenticated HTTPS/WSS signaling service reachable over both paths is needed
before claiming automatic cross-network recovery. No such service is provisioned.
[Signaling](https://webrtc.org/getting-started/peer-connections)

Direct host connectivity can work in a controlled reachable network. Carrier NAT,
enterprise firewalls or blocked UDP can prevent it. Operator-supplied STUN/TURN
may be needed; TURN requires a reachable deployment, credentials, capacity and
approval for those destinations. No public STUN/TURN endpoint is hardcoded or
contacted by opening the page. Relay selection still does not establish the
Mac's underlying interface. TURN allocations may also need recovery on a changed
network; a relay is not a continuity guarantee.
[TURN requirements](https://webrtc.org/getting-started/turn-server)

## Measurements and verification

Browser stats can expose packet/frame/sample counters and selected ICE-pair
changes. The prototype exports only allowlisted numeric fields and enum labels;
raw candidates, addresses, ports, SSRCs, track IDs, SDP and credentials are omitted.
Pair identity changes are counted locally and exported as a generation number;
this is not physical egress proof. Unknown metrics stay null.
[WebRTC Statistics](https://www.w3.org/TR/webrtc-stats/)

Verifying Wi-Fi/cellular paths without changing routes is possible **as a separate
approved measurement**, by correlating the call's transport with captures on en0
and en6 and remote-side observations. Browser stats alone cannot do it. Private
correlation material must remain owner-only. Same-Mac calls, public-IP lookup,
iPhone USB presence, socket-option readback from an unrelated HTTPS request, and
an observed Wi-Fi icon change are insufficient. The prototype performs no capture.

## Permissions and practical blockers

Camera/microphone require browser permission and macOS privacy approval for that
browser. Remote playback may require a user gesture; headphones avoid feedback.
getUserMedia requires a secure context (localhost is the normal local-development
case; arbitrary HTTP LAN hosting is not equivalent). macOS local-network prompts,
managed-device policy, university restrictions, captive portals, iPhone trust/
tethering availability, cellular service and concurrent Wi-Fi/en6 availability
remain unverified. Never bypass a permission or certificate warning.
[Media capture requirements](https://www.w3.org/TR/mediacapture-streams/)

A Python aiortc/aioice implementation would need additional dependencies and a
careful, tested transport adapter to bind every relevant ICE/STUN/TURN socket.
Merely supplying a source address is not the existing IP_BOUND_IF guarantee.
Native libwebrtc/Network.framework integration is another future research path,
not available through the browser's standard JavaScript API. No unsupported
private API hook or browser flag is used here.

## Comparison with system-wide Network Extension/VPN

| Approach | Reach | Requirements | Continuity limit |
| --- | --- | --- | --- |
| Controlled browser call | Only its own media/session | Camera/mic, secure origin, signaling, potentially TURN | ICE recovery possible; named-interface steering unavailable |
| Native owned-socket call | Only its own transports | Native media/ICE stack and tested interface binding | Requires transport/session recovery design; not built here |
| Network Extension / VPN | Traffic routed into an approved tunnel | Signed native app/provider, entitlements, user/admin approval, tunnel server and testing | Stable overlay endpoint and resilient outer transport may help; tunnel alone does not make handover seamless |

Apple's packet-tunnel provider forwards traffic through a VPN server; it is not a
small extension to this Python dashboard. Deployment requires the appropriate
Network Extension capability/signing configuration. This introduces a separate
security/deployment project and may affect other applications. It is unsuitable
as an unvalidated last-minute competition modification. No profile, extension,
route, DNS, firewall or service-order changes are made.
[Apple packet tunnel](https://developer.apple.com/documentation/networkextension/packet-tunnel-provider),
[Apple entitlements](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.networking.networkextension)

## Phase boundary and recommendation

Proceed only with the limited controlled-call implementation described above.
An automatic en0→en6 media migration claim remains blocked by browser interface
control, unprovisioned resilient cross-network signaling/TURN and absent approved
path/continuity measurements. Keep the frozen competition dashboard as the EDGE
fallback. Promote this feature only after the protocol in PROTOCOL.md passes;
never present mocked tests or a local call as measured cellular handover.
