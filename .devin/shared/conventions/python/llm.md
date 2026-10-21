# Python LLM conventions

Model-using services, layered on [backend](backend.md) and
[observability](observability.md). [retrieval](retrieval.md) owns what to do with a corpus.
Confirm current model IDs through official docs rather than memory.

## One path for every model call

Every model call goes through one path, whatever implements it. That path emits uniform
telemetry — latency, errors, retries, fallbacks, served model version, tokens — and carries
attribution tags for company, product and feature as resource attributes, so cost per product is
a query rather than an investigation. Trace context propagates through it under the OpenTelemetry
GenAI semantic conventions, so a model call appears inside the agent's own trace rather than
beside it.

The application stays provider-agnostic: **the model is configuration, pinned by version**, and no
provider-specific code reaches application logic.

The intended end state is a gateway service we run. A shared client library is the acceptable
interim while that is unbuilt. The difference is worth knowing, because only a service can enforce
budgets across applications, change routing without a redeploy, grant third-party access without
sharing keys, and see calls it was never imported into.

Frontier models are reached through this path. We own no inference hardware.

## Choosing a framework

One framework per project, never two in the same one.

- **Pydantic AI** is the default — what to reach for absent a reason. It suits typed structured
  outputs, provider portability, and tests that run without live model calls.
- **LangGraph** when explicit branching, checkpointed state, resumable runs or human-interrupt
  flows dominate the design, or the people building it already know that ecosystem well. Write the
  reason down.
- **No framework at all** — the provider SDK directly — when distributing a library to third
  parties, or writing a throwaway script. A framework in a distributed library imposes itself on
  every consumer.

Whichever path: orchestration patterns stay project-owned and framework-independent, so
swapping the framework does not rewrite the orchestration. The shared library has no home
for them yet.
<!-- TODO(circeus): move them into the shared library once it owns an orchestration module. -->
No provider-specific code sits in application logic, tracing is OpenTelemetry, and the eval
gate applies identically.

## Layout and prompts

Agent construction and orchestration under `app/service/ai/`; prompt constants under
`app/repository/ai/*_prompts.py`; persisted results through repositories.

Prompts, skills and templates live in the repository next to the code they serve — versioned,
reviewed, and deployed atomically with it. A prompt is not runtime configuration.

## Agent construction

Use a typed output model, and build it dynamically only when the fields genuinely vary. Keep the
two retry budgets separate: the agent's own retry covers schema validation, the provider client's
covers transient transport errors. Conflating them turns one bad response into several paid calls.

Use temperature 0 for extraction and classification, and always set an explicit output-token limit.

**An agent calls only external tools on an approved list**, and each tool carries its own credential rather
than sharing one. A tool that changes state in someone else's system needs the delegation rule in
[auth patterns](patterns/auth-patterns.md) and leaves an audit record.

**Code an agent wrote never runs in the application's own process.** Use the provider's sandbox
first and an isolated container second. A model that can write code and a process that can execute
it are only safe apart.

## Provider

Wrap the providers in one model object. The worked example: select the client with
`ModelHostEnum.BEDROCK` or `ModelHostEnum.ANTHROPIC` and wrap both in a single `AnthropicModel`,
where Bedrock uses its regional model ID and direct Anthropic the bare one. Production API keys
come from the project's secret-resolution seam, never from a committed value.

## Observability and cost

- Instrument through the shared library's adapter; see [observability](observability.md) for the
  contract and what is scrubbed.
- Model message attributes are not scrubbed by default. When prompts, completions, tool arguments
  or results may contain sensitive data, disable content capture and keep timing, model metadata,
  token usage and cost.
- Wrap each run in both a span and `circlex.context`'s `audit_context_manager`.
- The audit record carries `ai_model_name`, `ai_operation_name`, `filename`, `ai_request_payload`,
  `ai_response_payload`, `ai_usage_tokens` and `ai_cost_usd`.
- Where a GenAI semantic convention already names the same fact, emit the standard attribute
  instead of the private one — a private name for a standardised fact costs portability and buys
  nothing. The model, the operation and the token counts have standard attributes; confirm the
  exact names against the semantic-convention version in use rather than from memory. `filename`,
  the two payload fields and `ai_cost_usd` have no standard equivalent and stay as they are.
- Record token usage and per-call cost, then call `update_audit_context(ai_cost_usd=cost)`.

Price by exact model ID using input and output per-million rates. Capture every call.

## Budgets and errors

Input budget is context window minus max output. Estimate document tokens with a ~0.9 safety margin, chunk oversized inputs to `max_pages_per_chunk`, and identify chunk context to avoid duplicate boundary rows. Stream large outputs.

Map provider failures onto the domain error classes the
[error model](backend.md#errors-and-io) owns: rate limit, HTTP 529 overload, bad request or
maximum tokens, other API error, unknown. Unwrap `ModelHTTPError.__cause__` first. Never leak a
raw provider exception through a per-call HTTP exception — the fixed-public-detail rule there is
what keeps a provider's message out of the response.

## Dependencies

Pin the dependencies the selected path actually uses, in `[project].dependencies`: the provider
SDK always, the framework only if one was chosen, and the observability extras matching both. A
project on Pydantic AI pins `pydantic-ai-slim`, `anthropic` and `logfire[anthropic,pydantic-ai]`;
one on another path pins its own equivalents. Add the shared-library extras the code imports.
