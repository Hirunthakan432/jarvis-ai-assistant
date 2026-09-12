"""Native tool loops. Remote content never gets a path to approving actions."""
import json

MAX_ROUNDS = 5
MAX_CALLS = 12


class Cancelled(Exception):
    pass


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled()


def call_tool(registry, name, arguments, on_event, cancel):
    check_cancel(cancel)
    try:
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        result = registry.execute(name, arguments)
    except (ValueError, TypeError):
        result = {'status': 'error', 'error': 'Tool arguments must be a JSON object.'}
    if on_event:
        on_event(name, result)
    return json.dumps(result, ensure_ascii=False)


def generate(client, provider, model, messages, registry, on_delta=None, cancel=None, on_event=None):
    if provider in {'openai', 'ollama'}:
        return openai_loop(client, model, messages, registry, on_delta, cancel, on_event)
    if provider == 'anthropic':
        return anthropic_loop(client, model, messages, registry, on_delta, cancel, on_event)
    if provider == 'gemini':
        return gemini_loop(client, model, messages, registry, on_delta, cancel, on_event)
    raise ValueError('Unsupported provider.')


def openai_loop(client, model, messages, registry, on_delta, cancel, on_event):
    transcript = list(messages)
    schemas = [{'type': 'function', 'function': schema} for schema in registry.schemas()]
    count = 0
    for _ in range(MAX_ROUNDS):
        check_cancel(cancel)
        kwargs = dict(model=model, messages=transcript)
        if schemas:
            kwargs['tools'] = schemas
        if on_delta:
            stream = client.chat.completions.create(**kwargs, stream=True)
            text, calls = '', {}
            try:
                for chunk in stream:
                    check_cancel(cancel)
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta.content:
                        text += delta.content
                        on_delta(delta.content)
                    for part in delta.tool_calls or []:
                        call = calls.setdefault(part.index, {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                        if part.id: call['id'] = part.id
                        if part.function:
                            call['function']['name'] += part.function.name or ''
                            call['function']['arguments'] += part.function.arguments or ''
            finally:
                stream.close()
            calls = [calls[key] for key in sorted(calls)]
        else:
            response = client.chat.completions.create(**kwargs).choices[0].message
            text = response.content or ''
            calls = [{'id': c.id, 'type': 'function', 'function': {'name': c.function.name, 'arguments': c.function.arguments}}
                     for c in response.tool_calls or []]
        if not calls:
            return text
        count += len(calls)
        if count > MAX_CALLS:
            raise ValueError('Tool limit reached. Please split the request into smaller steps.')
        transcript.append({'role': 'assistant', 'content': text or None, 'tool_calls': calls})
        for call in calls:
            content = call_tool(registry, call['function']['name'], call['function']['arguments'], on_event, cancel)
            transcript.append({'role': 'tool', 'tool_call_id': call['id'], 'content': content})
    raise ValueError('Tool round limit reached. Please split the request into smaller steps.')


def anthropic_loop(client, model, messages, registry, on_delta, cancel, on_event):
    transcript = [dict(m) for m in messages[1:]]
    schemas = [{'name': s['name'], 'description': s['description'], 'input_schema': s['parameters']} for s in registry.schemas()]
    count = 0
    for _ in range(MAX_ROUNDS):
        check_cancel(cancel)
        kwargs = dict(model=model, max_tokens=2048, system=messages[0]['content'], messages=transcript)
        if schemas:
            kwargs['tools'] = schemas
        if on_delta:
            with client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    check_cancel(cancel)
                    on_delta(text)
                response = stream.get_final_message()
        else:
            response = client.messages.create(**kwargs)
        calls = [block for block in response.content if block.type == 'tool_use']
        if not calls:
            return '\n'.join(block.text for block in response.content if block.type == 'text')
        count += len(calls)
        if count > MAX_CALLS: raise ValueError('Tool limit reached.')
        transcript.append({'role': 'assistant', 'content': [b.model_dump(exclude_none=True) for b in response.content]})
        results = [{'type': 'tool_result', 'tool_use_id': c.id,
                    'content': call_tool(registry, c.name, c.input, on_event, cancel)} for c in calls]
        transcript.append({'role': 'user', 'content': results})
    raise ValueError('Tool round limit reached.')


def gemini_loop(client, model, messages, registry, on_delta, cancel, on_event):
    from google.genai import types
    contents = [types.Content(role='model' if m['role'] == 'assistant' else 'user',
                              parts=[types.Part.from_text(text=m['content'])]) for m in messages[1:]]
    schemas = [types.FunctionDeclaration(name=s['name'], description=s['description'], parameters_json_schema=s['parameters']) for s in registry.schemas()]
    config = types.GenerateContentConfig(system_instruction=messages[0]['content'],
        tools=[types.Tool(function_declarations=schemas)] if schemas else None,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
    count = 0
    for _ in range(MAX_ROUNDS):
        check_cancel(cancel)
        # Preserve returned parts, including thought signatures, across function turns.
        if on_delta:
            stream = client.models.generate_content_stream(model=model, contents=contents, config=config)
            parts, text = [], ''
            try:
                for chunk in stream:
                    check_cancel(cancel)
                    if not chunk.candidates or not chunk.candidates[0].content:
                        continue
                    for part in chunk.candidates[0].content.parts or []:
                        parts.append(part)
                        if part.text and not part.thought:
                            text += part.text
                            on_delta(part.text)
            finally:
                if hasattr(stream, 'close'): stream.close()
            content = types.Content(role='model', parts=parts)
        else:
            response = client.models.generate_content(model=model, contents=contents, config=config)
            if not response.candidates or not response.candidates[0].content:
                return ''
            content = response.candidates[0].content
            text = ''.join(p.text for p in content.parts or [] if p.text and not p.thought)
        calls = [p.function_call for p in content.parts or [] if p.function_call]
        if not calls:
            return text
        count += len(calls)
        if count > MAX_CALLS: raise ValueError('Tool limit reached.')
        contents.append(content)
        parts = [types.Part.from_function_response(name=c.name,
                    response=json.loads(call_tool(registry, c.name, dict(c.args or {}), on_event, cancel))) for c in calls]
        contents.append(types.Content(role='user', parts=parts))
    raise ValueError('Tool round limit reached.')


def describe_image(client, provider, model, image, question):
    if provider in {'openai', 'ollama'}:
        response = client.chat.completions.create(model=model, messages=[{'role': 'user', 'content': [
            {'type': 'text', 'text': question}, {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,'+image}}]}])
        return response.choices[0].message.content
    if provider == 'anthropic':
        response = client.messages.create(model=model, max_tokens=2048, messages=[{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': image}},
            {'type': 'text', 'text': question}]}])
        return '\n'.join(p.text for p in response.content if p.type == 'text')
    if provider == 'gemini':
        import base64
        from google.genai import types
        return client.models.generate_content(model=model, contents=[
            types.Part.from_bytes(data=base64.b64decode(image), mime_type='image/jpeg'), question]).text
    raise ValueError('Unsupported vision provider.')
