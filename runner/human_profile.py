import random
import anyio

class HumanProfile:
    def __init__(self, profile_name=None):
        self.profile = profile_name or "default"
        self.min_delay = random.uniform(2.0, 4.0)
        self.max_delay = random.uniform(5.0, 9.0)
        self.typing_speed = random.randint(180, 300)
        self.scroll_jitter = random.uniform(0.5, 1.5)

    async def type_delay(self, text):
        chars_per_second = self.typing_speed / 60.0
        delay_per_char = 1.0 / chars_per_second
        total_delay = len(text) * delay_per_char
        await anyio.sleep(total_delay)

    async def click_delay(self):
        delay = random.uniform(self.min_delay, self.max_delay)
        await anyio.sleep(delay)

    async def scroll_pause(self):
        await anyio.sleep(random.uniform(0.5, 1.5))

    @classmethod
    def random(cls):
        return cls()
