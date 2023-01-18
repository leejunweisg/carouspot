from typing import List


def split_message(message: str, max_length=4096) -> List[str]:
    """Splits a long message into smaller parts that is within Telegram's maximum message length"""

    # if message is within limits, just send as-is
    if len(message) <= max_length:
        return [message]

    # splitting is required
    messages = []
    parts = message.split("\n\n")
    temp = ""
    for p in parts:
        if (len(temp) + len(p) + 2) < max_length:
            temp += p + "\n\n"
        else:
            messages.append(temp)
            temp = ""

    return messages
