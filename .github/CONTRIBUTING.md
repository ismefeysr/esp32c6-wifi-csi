# Contributing

Thank you for your interest in this project!

This repository is a **university course project** (Embedded Systems, EEE). Bug reports, questions and suggestions are very welcome. Because the project is graded, larger feature contributions may not be merged until the course has finished, so please open an issue to discuss a change before working on it.

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Reporting bugs and asking questions

Use the [issue templates](https://github.com/ismefeysr/esp32c6-wifi-csi/issues/new/choose). For bugs, please include:

- what you ran (command, board, port) and what you expected
- the ESP-IDF version (`idf.py --version`) and Python version
- relevant serial output or a few `CSI_DATA` lines, if the problem involves CSI parsing

Security issues should **not** be reported in public issues; see [SECURITY.md](SECURITY.md).

## Development setup

```bash
git clone --recursive https://github.com/ismefeysr/esp32c6-wifi-csi.git
cd esp32c6-wifi-csi

# Python tools and tests
python3 -m venv .venv
.venv/bin/pip install -r analysis/requirements-dev.txt
.venv/bin/python -m pytest

# Firmware (ESP-IDF v5.5)
. ~/esp/esp-idf/export.sh
cd firmware/csi_recv && idf.py set-target esp32c6 build
```

## Pull request guidelines

1. Fork the repository and create a branch from `main`.
2. Keep each pull request focused on one change.
3. **Tests:** changes to `analysis/` should come with tests in `tests/`, and `pytest` must pass.
4. **Firmware:** both applications must build for `esp32c6`. Code shared by both applications belongs in `firmware/components/`.
5. **Upstream:** do not modify `external/esp-csi`. It is kept as an unmodified upstream reference.
6. **Data:** never commit recorded datasets (`data/` is ignored), and never present synthetic data as real measurements.
7. **Language:** write all code, comments, documentation and commit messages in English.

CI runs the Python tests and both firmware builds on every pull request.

## Commit messages

Use a short imperative subject line (around 50 characters, e.g. "Add OLED status task"), followed by a blank line and a body explaining **what** changed and **why**.

## License

By contributing, you agree that your contributions are licensed under the project's [MIT License](../LICENSE).
