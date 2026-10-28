"""Application wake words load through the unmodified upstream LVA discovery."""
import sys

import pytest

from reachy_mini_ha_voice.runtime import VENDOR, WAKEWORDS

pytest.importorskip("pymicro_wakeword")


def test_lva_discovers_and_loads_xiao_pai_next_to_upstream_models():
    if str(VENDOR) not in sys.path:
        sys.path.insert(0, str(VENDOR))
    from linux_voice_assistant.models import WakeWordType
    from linux_voice_assistant.wake_word import find_available_wake_words
    from pymicro_wakeword import MicroWakeWord

    available = find_available_wake_words([VENDOR / "wakewords", WAKEWORDS], "stop")
    assert "okay_nabu" in available  # upstream models stay available
    xiao_pai = available["xiao_pai"]
    assert xiao_pai.type == WakeWordType.MICRO_WAKE_WORD
    assert xiao_pai.wake_word == "小派小派"
    model = MicroWakeWord.from_config(WAKEWORDS / "xiao_pai.json")
    assert model.wake_word == "小派小派"
