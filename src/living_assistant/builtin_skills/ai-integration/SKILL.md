---
name: ai-integration
description: "Add AI/LLM features to software: prompts, model calls, structured output, evaluation and fallbacks - use for AI engineering tasks."
---

# Ai integration

## When to use
A product needs a model call: summarizing, classifying, extracting, chatting or generating.

## Steps
1. Define exactly what goes in and what must come out (prefer JSON with a fixed shape).
2. Write the prompt with the task, the output format and 1-2 examples; keep it short.
3. Call the model through the configured provider (a local llama.cpp/OpenAI-compatible endpoint by default); set timeouts and handle errors.
4. Validate the model output; on invalid output retry once, then fall back gracefully.
5. Add a tiny evaluation: 3-5 sample inputs with expected outputs, and run it.

## Rules and checks
- Never send user data to an external API unless the user allowed it.
- API keys come from environment variables, never from code.
