import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    @classmethod
    def API_KEY(cls):
        return os.getenv("OPENWEBUI_API_KEY")

    @classmethod
    def BASE_URL(cls):
        return os.getenv("OPENWEBUI_BASE_URL")

    @classmethod
    def validate(cls):
        missing = [k for k, v in {
            "OPENWEBUI_API_KEY": cls.API_KEY(),
            "OPENWEBUI_BASE_URL": cls.BASE_URL(),
        }.items() if not v]
        if missing:
            raise ValueError(f"Missing core environment variables: {', '.join(missing)}")
