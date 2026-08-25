from serial_terminal.filters import LineFilter, is_visible
from serial_terminal.formatting import log_file_name, sanitize_port


def test_port_names_are_sanitized_for_log_files() -> None:
    assert sanitize_port("/dev/ttyACM0") == "dev_ttyACM0"
    assert log_file_name("/dev/tty ACM0", "20260825_120000") == "log_dev_tty_ACM0_20260825_120000.log"


def test_plain_and_regex_filters_are_combined() -> None:
    global_filter = LineFilter.parse("error")
    port_filter = LineFilter.parse("/RX\\s+42/")
    assert is_visible("ERROR RX 42", global_filter, port_filter)
    assert not is_visible("ERROR TX 42", global_filter, port_filter)
    assert not is_visible("INFO RX 42", global_filter, port_filter)
