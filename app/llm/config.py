import os

from dotenv import load_dotenv


load_dotenv()



class LLMConfig:


    DEEPSEEK_API_KEY = os.getenv(
        "DEEPSEEK_API_KEY"
    )


    DEFAULT_PROVIDER = "deepseek"
