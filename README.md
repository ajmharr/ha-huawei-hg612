# Huawei HG612 for Home Assistant

A read-only Home Assistant custom integration for monitoring a Huawei EchoLife
HG612 VDSL2 modem through its Telnet interface. It has been developed and
validated against unlocked B030SP08 firmware on an HG612 3B.

The integration reports the physical DSL link. A synchronized line means the
modem reports `Status: Showtime`; it does **not** mean PPPoE is connected or
that internet access is available.

## Features

- UI configuration with host, Telnet username, Telnet password, and polling
  interval
- One shared asynchronous poll for every entity, defaulting to 60 seconds
- DSL synchronization status, sync and attainable rates, SNR, attenuation,
  transmit power, mode, profile, and uptime
- Downstream and upstream FEC, CRC, ES, SES, UAS, LOS, and LOF counters
- Raw modem counter resets preserved for correct Home Assistant long-term
  statistics handling
- Automatic entity unavailability and recovery after communication failures
- Redacted diagnostics with no credentials or raw Telnet response
- No modem configuration or connectivity control

## Installation

### HACS custom repository

Until this integration is published in the default HACS repository:

1. Open HACS in Home Assistant.
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/ajmharr/ha-huawei-hg612` with type
   **Integration**.
4. Find **Huawei HG612** in HACS and download it.
5. Restart Home Assistant.

No release has been published yet, so this path is prepared but not available
until the repository is pushed and an approved release is created.

### Manual test installation

Copy `custom_components/huawei_hg612` into the Home Assistant configuration
directory so the resulting path is:

```text
<config>/custom_components/huawei_hg612/manifest.json
```

Restart Home Assistant after copying or updating the files. Home Assistant
installs the pinned `telnetlib3` requirement from the integration manifest.

## Configuration

1. Go to **Settings → Devices & services**.
2. Select **Add integration**.
3. Search for **Huawei HG612**.
4. Enter the modem IP address or hostname, Telnet username, Telnet password,
   and polling interval.

The polling interval defaults to 60 seconds and accepts 30–3600 seconds. It can
be changed later from the integration's **Configure** action.

Each poll creates one short Telnet session, authenticates, runs only `sh` and
`xdslcmd info --stats`, captures the complete response, and closes the
transport. Every entity consumes that single result.

## Entities

The integration creates 27 sensors and one binary sensor:

- downstream/upstream sync and maximum attainable rates
- downstream/upstream SNR margin, attenuation, and transmit power
- DSL uptime, mode, and VDSL profile
- downstream/upstream FEC, CRC, ES, SES, UAS, LOS, and LOF totals
- **DSL synchronized**, based only on the modem's DSL status

Measurement entities use Home Assistant measurement state classes. Modem error
counters use `total_increasing`; when the modem restarts or DSL resynchronizes,
the lower raw value is exposed directly so Home Assistant can identify a new
counter cycle. The integration never adds an offset or invents continuity.

If a complete modem response legitimately omits an unsupported value, only
that entity is unavailable. A timeout, disconnect, or incomplete response
marks all coordinator-backed entities unavailable until a later successful
poll.

## Security

Telnet is unencrypted: credentials and modem data travel in plaintext. Restrict
port 23 to a trusted management network and do not expose it to the internet.
This integration does not modify the modem firewall, DSL settings, interfaces,
WAN connectivity, or PPPoE configuration.

Credentials are stored in the Home Assistant config entry. Diagnostics redact
the host, username, and password and exclude the raw command response.

## Standalone read-only verification

The Phase 1 verifier remains available from a development checkout. It prompts
for both credentials with terminal echo disabled:

```bash
python -m custom_components.huawei_hg612.verify
```

To create an owner-only raw response file without overwriting an existing file:

```bash
python -m custom_components.huawei_hg612.verify --save-raw hg612-stats.txt
```

## Development and tests

The integration targets current Home Assistant releases. The committed test
container pins Home Assistant 2026.10.4 and runs with networking disabled:

```bash
docker build -f .docker/Dockerfile.test -t ha-huawei-hg612-test:2026.10.4 .
docker run --rm --network none -v "$PWD:/workspace" \
  ha-huawei-hg612-test:2026.10.4 pytest -q
```

Tests use simulated Telnet sessions and representative synthetic output derived
from the validated B030SP08 response format. They do not require a modem or a
running Home Assistant installation.

## Parser behavior and limitations

The parser keeps total, current/previous 15-minute, current/previous daily, and
since-link counter sections separate. Missing values remain `None`; they are
never reported as zero. Framing, bearer-detail, retransmission, and G.INP
diagnostics are recognized as valid output but are not exposed as entities.

The B030SP08 upstream attenuation placeholder of `0.0 dB` is retained in parsed
diagnostics but is not exposed as a valid entity state.
