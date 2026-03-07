import pathlib
from ada.ui.llm_runtime import build_client_and_model
path_to_here = pathlib.Path(__file__).parent.resolve()

# https://cookbook.openai.com/examples/how_to_call_functions_with_chat_models
# https://platform.openai.com/docs/guides/function-calling?lang=python
# https://platform.openai.com/docs/guides/fine-tuning/fine-tuning-examples

def sendToOpenAI(ipt, functionData = None, model=None):
    client, model = build_client_and_model(model)

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
