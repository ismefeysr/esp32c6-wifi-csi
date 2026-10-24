# Security Policy

## Scope

This is a research and course project, not a production system. It runs on a local, router-less ESP-NOW link and sends no data to the internet. Security-relevant areas include:

- the firmware in `firmware/` (ESP-NOW handling, CSI callback, serial output)
- the host tools in `analysis/`, which parse serial data and log files

Please keep in mind that the ESP-NOW link is deliberately **unencrypted** (broadcast frames are needed for CSI capture), so anyone within radio range can send or receive frames. This is a known property of the design, not a vulnerability.

## Supported versions

Only the latest commit on `main` is maintained.

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report them privately through GitHub's [private vulnerability reporting](https://github.com/ismefeysr/esp32c6-wifi-csi/security/advisories/new) (*Security → Report a vulnerability*). Please include:

- a description of the issue and its impact
- steps to reproduce, or a proof of concept
- affected files or components

You can expect an initial response within about a week. Because this is a student project, fixes are provided on a best-effort basis.

Vulnerabilities in ESP-IDF or esp-csi themselves should be reported to [Espressif](https://www.espressif.com/en/support/product-security-advisories) directly.
