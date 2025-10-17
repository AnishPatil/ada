import os
from openai import OpenAI
import json
import pathlib
path_to_here = pathlib.Path(__file__).parent.resolve()

# https://cookbook.openai.com/examples/how_to_call_functions_with_chat_models
# https://platform.openai.com/docs/guides/function-calling?lang=python
# https://platform.openai.com/docs/guides/fine-tuning/fine-tuning-examples

def sendToOpenAI(ipt, functionData = None, model="gpt-4o"):
    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        organization=os.environ.get("OPENAI_ORG"),
    )

    if functionData is None:
        raise ValueError('Did not recieve any function data')


    tools = [{"type":"function"} | v for v in functionData]

    response = client.responses.create(
        model=model,
        # instructions="Always output your response by using a tool.  Do not respond to the user or ask a question under any circumstances.",
        tools=tools,
        input = [{
            'role': 'user',
            'content': ipt,
        }],
        tool_choice="auto",
    )

    return response



# strict: true
# tool_choice: 'required'