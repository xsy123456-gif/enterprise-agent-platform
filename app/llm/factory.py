from app.llm.config import LLMConfig

from app.llm.providers.deepseek import DeepSeekLLM



def create_llm():


    provider = (
        LLMConfig.DEFAULT_PROVIDER
    )


    if provider == "deepseek":


        return DeepSeekLLM(

            api_key=
            LLMConfig.DEEPSEEK_API_KEY

        )


    raise ValueError(
        f"Unsupported LLM provider:{provider}"
    )
