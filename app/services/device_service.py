"""Find out what kind of device made a request, using its User-Agent."""

from user_agents import parse

from app.models.click import DeviceType


def detect_device_type(user_agent: str | None) -> DeviceType:
    """Return the device type for a User-Agent string.

    Real browsers always send a User-Agent, so a missing one almost
    always means a script or a bot.

    The checks run in this order: bot, tablet, mobile. Anything else
    is treated as a desktop.
    """
    if not user_agent or not user_agent.strip():
        return DeviceType.BOT

    parsed = parse(user_agent)
    if parsed.is_bot:
        return DeviceType.BOT
    if parsed.is_tablet:
        return DeviceType.TABLET
    if parsed.is_mobile:
        return DeviceType.MOBILE
    return DeviceType.DESKTOP
