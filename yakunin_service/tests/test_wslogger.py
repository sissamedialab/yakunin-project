"""Test the WebSocket logger."""

import datetime
import logging

from yakunin_service.views import WSLogger


def test_wslogger_jsondumps_errors(mocker, caplog):
    """Ensure that WSLogger does not die on non-serializable feedback messages."""
    # A note about caplog and yakunin logger
    #
    # The "caplog" fixture alone did not capture the log messages.
    # I also tried with specific config for the logger as in `caplog.set_level(..., logger="yakunin")`
    # but with no effect.
    #
    # Since the log messages is emitted on the stderr, I tried capsys
    # as in `assert repr(now) in capsys.readouterr().err`
    # but with not luck.
    #
    # In the end I had to force yakunin's logger to "propagate" (by default it does not)
    # This is probably because of
    #
    # ⚠
    # The caplog fixture adds a handler to the root logger to capture
    # logs. If the root logger is modified during a test, for example with
    # logging.config.dictConfig, this handler may be removed and cause no
    # logs to be captured. To avoid this, ensure that any root logger
    # configuration only adds to the existing handlers.
    #
    # https://docs.pytest.org/en/stable/how-to/logging.html#caplog-fixture
    #
    yakunin_logger = logging.getLogger("yakunin")
    yakunin_logger.propagate = True

    mocker.patch("yakunin_service.views.WSLogger.__post_init__")
    wslogger = WSLogger(feedback_ws_url="anything")
    wslogger.__post_init__.assert_called_once()

    wslogger.feedback_ws = mocker.MagicMock()

    wslogger._send(result="anything", msg="anything", data="anything")  # noqa: SLF001
    wslogger.feedback_ws.send.assert_called_once()

    # The _send method json-serializes result, msg and data,
    # so a datetime object should trigger a TypeError;
    # here we ensure that this does not happen,
    # and that a "normal" log message is emitted instead
    now = datetime.datetime.now()  # noqa: DTZ005
    wslogger._send(result="anything", msg="anything", data=now)  # noqa: SLF001
    wslogger.feedback_ws.send.assert_called_once()
    assert repr(now) in caplog.text
