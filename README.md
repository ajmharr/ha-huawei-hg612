# Huawei HG612 monitoring for Home Assistant

This repository is being developed as a lightweight Home Assistant custom
integration for monitoring a Huawei EchoLife HG612 VDSL2 modem. It is currently
at **Phase 1**: a standalone asynchronous Telnet client and a pure parser for
`xdslcmd info --stats` output.

No Home Assistant entities or configuration flow are included yet.

## Phase 1 layout

```text
src/huawei_hg612/
  client.py       asynchronous Huawei ATP/BusyBox Telnet workflow
  parser.py       section-aware DSL statistics parser
  models.py       typed command and statistics models
  exceptions.py   communication and protocol failures
tests/
  fixtures/       explicitly synthetic modem responses
  test_client.py  simulated Telnet sessions
  test_parser.py  parser and counter reset tests
```

The modem library does not import Home Assistant. During Phase 2 these small
modules can be placed inside `custom_components/huawei_hg612` without requiring
users to install a separate local package. The only runtime dependency is the
pure-Python `telnetlib3` package, pinned for reproducible installation. A future
Home Assistant manifest will also pin this requirement as required by Home
Assistant.

## Response completeness

Missing statistics and incomplete transport responses are deliberately
different conditions:

- A command that returns normally to the BusyBox prompt is a `COMPLETE`
  response. Individual values may still be absent or reported as `N/A`; the
  parser represents those values as `None` and never invents zeroes.
- A timeout or disconnect before the prompt returns raises
  `IncompleteResponseError`. The exception retains the partial output for
  diagnostics. It must not be treated as a successful poll.
- The parser can parse partial diagnostic text when it is explicitly wrapped
  in a `CommandResponse` marked `INCOMPLETE`; the resulting statistics remain
  marked incomplete.

This distinction lets the future Home Assistant coordinator keep entities
available when a valid response omits an unsupported statistic, while marking
an update unsuccessful when communication truncates the response.

## Telnet workflow

Each poll uses a fresh connection and follows the modem-specific prompt flow:

1. Connect using `telnetlib3`, which handles Telnet option negotiation.
2. Recognise a username or password prompt and authenticate.
3. Wait for the Huawei `ATP>` prompt.
4. Run `sh` and wait for the BusyBox `#` prompt.
5. Run `xdslcmd info --stats` and collect output until `#` returns.
6. Attempt a clean logout and close the connection.

Connection, prompt, and command operations have independent timeouts. Passwords
and authentication exchanges are never logged.

## Parser behavior

The parser handles global line properties separately from counter reporting
periods. Recognised counter sections are:

- total
- current and previous 15-minute periods
- current and previous daily periods
- since-link

Repeated names such as `FEC` and `CRC` are stored beneath their section and do
not overwrite total counters. Unknown lines are retained in `unparsed_lines`,
and the original response is retained in `raw_output`. Counter decreases can be
detected explicitly with `detect_counter_resets`; missing counters are not
interpreted as resets.

## Development and tests

Python 3.9 or newer is required for the standalone package.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/pytest -q --cov=huawei_hg612 --cov-report=term-missing
```

Tests use simulated Telnet streams and synthetic DSL fixtures. They never
connect to a modem or Home Assistant installation.

## Security

Telnet sends credentials and modem data without encryption. Use this client
only on a trusted, access-controlled management network. This software does not
modify modem firewall settings, DSL settings, WAN connectivity, or PPPoE
configuration.

Credentials must be supplied by the caller and must not be placed in source
control. Phase 2 will store them through Home Assistant's configuration entry
mechanism and redact them from diagnostics.

## Current limitations

- Fixtures are synthetic and based on the illustrative excerpt supplied for
  development. The parser has not been validated against a complete HG612
  B030SP08 capture.
- Exact prompt spelling, prompt decoration, character encoding, Telnet option
  behavior, and the clean logout sequence still require read-only live-device
  validation in a later approved phase.
- The upstream attenuation value reported by some firmware may be meaningless;
  the parser preserves it but does not judge its validity.
- Phase 1 has no polling scheduler, retry policy, Home Assistant coordinator,
  entities, config flow, or diagnostics endpoint.
