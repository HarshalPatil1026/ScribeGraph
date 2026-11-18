TUTORIAL_TOPIC_PROMPT = """
You are the content strategist for a technical blog about AI and machine learning.
Category: {cat_label}

Articles already published in this category (newest first):
{history}

Choose ONE new tutorial topic for this category that:
- is not a repeat or near-repeat of anything above,
- builds naturally on what readers have already seen,
- can be taught in depth in a single 1,500 to 2,500 word article.

Reply with ONLY this JSON object and nothing else:
{{
  "topic": "Specific, concrete topic title",
  "subtopics": "3 to 5 comma-separated subtopics the article will cover"
}}
"""

TUTORIAL_GENERATION_PROMPT = """
You are a senior engineer and technical writer.
Category: {cat_label}
Topic: {topic}
Subtopics to cover: {subtopics}

{validator_feedback}

Write a complete, in-depth tutorial on this topic in Markdown.

Requirements:
- Audience: developers and students who know basic Python.
- Do NOT start with a top-level "# Title" line; the site shows the title separately.
  Open with a short introduction paragraph, then use "##" and "###" section headings.
- Explain the intuition first, then the details. Use concrete examples.
- Include runnable Python code blocks where they help (fenced with ```python).
- Use tables or lists where they make comparisons clearer. Bold key terms sparingly.
- Be accurate. Do not invent APIs, library functions, statistics or citations.
- End with a "## Key Takeaways" section of 4 to 6 bullet points.
- Length: about 1,500 to 2,500 words. No filler, no generic marketing language.
- Return only the article Markdown, not wrapped in a code block.
"""
