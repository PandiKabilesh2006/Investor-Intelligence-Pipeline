import google.generativeai as genai
import json

from app.config.settings import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-2.5-flash")


def parse_investor(markdown_content):

    prompt = f"""
    You are analyzing a venture capital firm's website.

    Extract ONLY information explicitly mentioned in the content.

    Return ONLY valid JSON in this exact format:

    {{
      "firm": "",
      "website": "",
      "focus_sectors": [],
      "investment_stage": [],
      "partners": []
    }}

    Rules:
    - focus_sectors should contain industries like AI, Fintech, SaaS, Healthcare, etc.
    - investment_stage should contain stages like Seed, Series A, Growth, etc.
    - partners should contain investor or partner names.
    - Do not hallucinate missing information.
    - If information is unavailable, return empty arrays.

    Website Content:
    {markdown_content}
    """

    response = model.generate_content(prompt)

    cleaned = (
        response.text
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    return json.loads(cleaned)