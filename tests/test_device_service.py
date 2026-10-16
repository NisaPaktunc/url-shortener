"""Tests for device detection, without any HTTP involved."""

import pytest

from app.models import DeviceType
from app.services.device_service import detect_device_type
from tests import sample_agents


@pytest.mark.parametrize(
    ("user_agent", "expected"),
    [
        (sample_agents.IPHONE, DeviceType.MOBILE),
        (sample_agents.ANDROID_PHONE, DeviceType.MOBILE),
        (sample_agents.IPAD, DeviceType.TABLET),
        (sample_agents.ANDROID_TABLET, DeviceType.TABLET),
        (sample_agents.WINDOWS_CHROME, DeviceType.DESKTOP),
        (sample_agents.MAC_SAFARI, DeviceType.DESKTOP),
        (sample_agents.GOOGLEBOT, DeviceType.BOT),
    ],
)
def test_detects_device_type(user_agent: str, expected: DeviceType) -> None:
    assert detect_device_type(user_agent) == expected


@pytest.mark.parametrize("user_agent", [None, "", "   "])
def test_missing_user_agent_is_a_bot(user_agent: str | None) -> None:
    assert detect_device_type(user_agent) == DeviceType.BOT


def test_unknown_user_agent_falls_back_to_desktop() -> None:
    assert detect_device_type("MyCoolApp/1.0") == DeviceType.DESKTOP
