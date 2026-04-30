import random, time

class HumanProfile:
    def __init__(self, profile_name=None):
        self.profile = profile_name or "default"
        self.min_delay = random.uniform(0.8, 2.0)
        self.max_delay = random.uniform(3.0, 6.0)
        self.typing_speed = random.randint(60, 120)
        self.scroll_jitter = random.uniform(0.5, 1.5)

    def type_delay(self, text):
        chars_per_second = self.typing_speed / 60.0
        delay_per_char = 1.0 / chars_per_second
        total_delay = len(text) * delay_per_char
        time.sleep(total_delay)

    def click_delay(self):
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)

    def scroll_pause(self):
        time.sleep(random.uniform(0.5, 1.5))
