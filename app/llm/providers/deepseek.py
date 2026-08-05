from openai import OpenAI


from app.llm.base import BaseLLM



class DeepSeekLLM(BaseLLM):


    provider = "deepseek"

    model = "deepseek-chat"

    base_url = "https://api.deepseek.com"



    def __init__(
        self,
        api_key
    ):

        self.client = OpenAI(

            api_key=api_key,

            base_url=self.base_url

        )



    def chat(
        self,
        messages,
        **kwargs
    ):


        response = self.client.chat.completions.create(

            model=self.model,

            messages=messages,

            temperature=kwargs.get(
                "temperature",
                0
            )

        )


        return response.choices[0].message.content
