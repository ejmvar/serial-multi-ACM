from pathlib import Path

from serial_terminal.cli import parse_args


def test_parse_serial_settings_and_ports() -> None:
    ports, settings, log_dir = parse_args([
        "/dev/ttyACM0", "/dev/ttyACM1", "--baudrate", "9600", "--bytesize", "7",
        "--parity", "e", "--stopbits", "1.5", "--timeout", "0.5", "--log-dir", "captures",
    ])
    assert ports == ["/dev/ttyACM0", "/dev/ttyACM1"]
    assert settings.baudrate == 9600
    assert settings.bytesize == 7
    assert settings.parity == "E"
    assert settings.stopbits == 1.5
    assert settings.timeout == 0.5
    assert log_dir == Path("captures")
