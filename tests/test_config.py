from config import Config
import os

def test_config_loading():
    os.environ["OPENWEBUI_API_KEY"] = "test_key"
    os.environ["OPENWEBUI_BASE_URL"] = "http://test.com"
    Config.validate()
    assert Config.API_KEY() == "test_key"

if __name__ == "__main__":
    test_config_loading()
    print("Config test passed!")
