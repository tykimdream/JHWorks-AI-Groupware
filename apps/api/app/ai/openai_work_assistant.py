import json
from time import perf_counter
from typing import Any, cast

from openai import OpenAI, OpenAIError

from app.ai.work_assistant import (
    MAX_TOOL_CALLS,
    MAX_TOOL_ROUNDS,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    TOOL_DEFINITIONS,
    EnterpriseToolExecutor,
    ToolExecution,
    ToolExecutionError,
    WorkAssistantProviderError,
    WorkAssistantProviderResult,
    WorkAssistantUsage,
)


class OpenAIWorkAssistantProvider:
    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        self._client = OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=1,
        )
        self._model = model

    def answer(
        self,
        message: str,
        executor: EnterpriseToolExecutor,
        safety_identifier: str,
    ) -> WorkAssistantProviderResult:
        started_at = perf_counter()
        input_items: list[Any] = [{"role": "user", "content": message}]
        executions: list[ToolExecution] = []
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        response_model = self._model
        create_response = cast(Any, self._client.responses.create)

        try:
            for round_number in range(1, MAX_TOOL_ROUNDS + 1):
                response = create_response(
                    model=self._model,
                    instructions=SYSTEM_PROMPT,
                    input=input_items,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    parallel_tool_calls=False,
                    max_output_tokens=1200,
                    prompt_cache_key=PROMPT_VERSION,
                    safety_identifier=safety_identifier,
                    store=False,
                )
                response_model = response.model or self._model
                if response.usage is not None:
                    input_tokens += response.usage.input_tokens
                    output_tokens += response.usage.output_tokens
                    total_tokens += response.usage.total_tokens

                function_calls = [
                    item for item in response.output if item.type == "function_call"
                ]
                if not function_calls:
                    answer = response.output_text.strip()
                    if not answer:
                        raise WorkAssistantProviderError(
                            "The work assistant returned no usable answer"
                        )
                    return WorkAssistantProviderResult(
                        answer=answer,
                        executions=executions,
                        provider="openai",
                        model=response_model,
                        usage=WorkAssistantUsage(
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=total_tokens,
                        ),
                        latency_ms=round((perf_counter() - started_at) * 1000),
                        round_count=round_number,
                    )

                if len(executions) + len(function_calls) > MAX_TOOL_CALLS:
                    raise WorkAssistantProviderError("The work assistant exceeded its tool limit")

                input_items.extend(
                    item.model_dump(mode="json", exclude_none=True) for item in response.output
                )
                for call in function_calls:
                    parsed = json.loads(call.arguments)
                    if not isinstance(parsed, dict):
                        raise ToolExecutionError("Tool arguments must be an object")
                    result = executor.execute(call.name, parsed)
                    executions.append(
                        ToolExecution(name=call.name, arguments=parsed, result=result)
                    )
                    input_items.append(
                        {
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": json.dumps(result, ensure_ascii=False),
                        }
                    )
        except (OpenAIError, json.JSONDecodeError, ToolExecutionError) as exc:
            raise WorkAssistantProviderError(
                "The work assistant provider is unavailable"
            ) from exc

        raise WorkAssistantProviderError("The work assistant exceeded its round limit")
