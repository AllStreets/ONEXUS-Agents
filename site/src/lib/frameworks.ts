// Framework registry. Slugs match pipeline/frameworks.py — keep in sync.

export type FrameworkInfo = {
  slug: string;
  name: string;
  description: string;
  url: string;
  glyph: string; // Lucide icon name (already in site/src/components/Icon.astro)
};

export const FRAMEWORKS: FrameworkInfo[] = [
  {
    slug: "langchain",
    name: "LangChain",
    description: "Composable framework for chaining LLM calls, tools, and memory.",
    url: "https://github.com/langchain-ai/langchain",
    glyph: "code",
  },
  {
    slug: "llamaindex",
    name: "LlamaIndex",
    description: "Data framework for connecting LLMs to private data via retrieval + indexes.",
    url: "https://github.com/run-llama/llama_index",
    glyph: "database",
  },
  {
    slug: "crewai",
    name: "CrewAI",
    description: "Multi-agent orchestration for role-playing autonomous workflows.",
    url: "https://github.com/joaomdmoura/crewAI",
    glyph: "network",
  },
  {
    slug: "autogen",
    name: "AutoGen",
    description: "Microsoft framework for multi-agent conversational LLM applications.",
    url: "https://github.com/microsoft/autogen",
    glyph: "network",
  },
  {
    slug: "smolagents",
    name: "smolagents",
    description: "Hugging Face minimal agent framework — code-first, transparent.",
    url: "https://github.com/huggingface/smolagents",
    glyph: "huggingface",
  },
  {
    slug: "dspy",
    name: "DSPy",
    description: "Programmatic framework for compiling structured LM pipelines.",
    url: "https://github.com/stanfordnlp/dspy",
    glyph: "scatter-chart",
  },
  {
    slug: "openai-agents-sdk",
    name: "OpenAI Agents SDK",
    description: "OpenAI's official SDK for building agentic applications.",
    url: "https://github.com/openai/openai-agents-python",
    glyph: "sparkles",
  },
  {
    slug: "anthropic-sdk",
    name: "Anthropic SDK",
    description: "Claude SDK usage — tool use, prompt caching, agent loops.",
    url: "https://github.com/anthropics/anthropic-sdk-python",
    glyph: "sparkles",
  },
  {
    slug: "mcp",
    name: "MCP",
    description: "Model Context Protocol servers — runnable via stdio.",
    url: "https://github.com/modelcontextprotocol",
    glyph: "play",
  },
  {
    slug: "transformers",
    name: "Transformers",
    description: "Hugging Face transformers library — pretrained models + inference.",
    url: "https://github.com/huggingface/transformers",
    glyph: "huggingface",
  },
  {
    slug: "gradio",
    name: "Gradio",
    description: "UI framework for ML demos — Spaces, components, event handlers.",
    url: "https://github.com/gradio-app/gradio",
    glyph: "monitor",
  },
];

export const FRAMEWORK_BY_SLUG: Record<string, FrameworkInfo> =
  Object.fromEntries(FRAMEWORKS.map((f) => [f.slug, f]));
