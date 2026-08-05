import requests


from llm.base import BaseLLM



class OllamaLLM(BaseLLM):


    def __init__(
        self,
        model,
        url="http://localhost:11434"
    ):

        self.model=model

        self.url=url



    def chat(
        self,
        messages,
        **kwargs
    ):


        response=requests.post(

            f"{self.url}/api/chat",

            json={

                "model":
                self.model,


                "messages":
                messages,


                "stream":
                False

            }

        )


        return response.json()["message"]["content"]
