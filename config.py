import os
from dotenv import load_dotenv

load_dotenv()


class Config:

    def __init__(self):
        self.BOT_TOKEN = os.getenv("BOT_TOKEN", "")
        self.NASA_API_KEY = os.getenv("NASA_API_KEY", "")

        missing = [k for k, v in {"BOT_TOKEN": self.BOT_TOKEN, "NASA_API_KEY": self.NASA_API_KEY}.items() if not v]
        if missing:
            raise RuntimeError(f"Отсутствуют переменные окружения: {', '.join(missing)}")


config = Config()
