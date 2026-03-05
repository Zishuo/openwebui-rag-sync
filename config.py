import os
from dotenv import load_dotenv
import urllib3

load_dotenv()

class Config:
    @classmethod
    def API_KEY(cls):
        return os.getenv("OPENWEBUI_API_KEY")

    @classmethod
    def BASE_URL(cls):
        return os.getenv("OPENWEBUI_BASE_URL")

    @classmethod
    def VERIFY_SSL(cls):
        # Default to True, allow "false" or "0" to disable
        val = os.getenv("OPENWEBUI_VERIFY_SSL", "true").lower()
        should_verify = val not in ("false", "0")
        if not should_verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return should_verify

    @classmethod
    def validate(cls):
        missing = [k for k, v in {
            "OPENWEBUI_API_KEY": cls.API_KEY(),
            "OPENWEBUI_BASE_URL": cls.BASE_URL(),
        }.items() if not v]
        if missing:
            raise ValueError(f"Missing core environment variables: {', '.join(missing)}")
