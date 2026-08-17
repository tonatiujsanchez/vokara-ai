"""Versioned prompts.

Each prompt is a constant with a versioned name. Changing the text **requires**
a new version; an existing one is never edited, because the evals pin the
version under test and a prompt that changes underneath them stops meaning
anything (contracts/llm-extraction.md, art. VI).

No clause of any prompt here names a provider or assumes a capability of one:
the prompt describes the task, not the model that runs it (art. XI).
"""
