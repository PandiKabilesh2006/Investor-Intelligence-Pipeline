import json
import time

from groq import Groq

from app.config.settings import GROQ_API_KEY


client = Groq(

    api_key=GROQ_API_KEY
)


def parse_investor(markdown_content):
    prompt = f"""
You are a venture capital intelligence
extraction system.

Your task is to extract structured investor
information from a VC firm's website.

Extract ONLY information explicitly mentioned
in the content.

Return ONLY valid JSON.

Use this EXACT schema:

{{
  "firm": "",
  "website": "",
  "focus_sectors": [],
  "investment_stage": [],
  "partners": []
}}

IMPORTANT RULES:

- Extract ONLY venture capital,
  investment firm, or investor information

- Do NOT extract startup founders

- Do NOT extract article authors

- Do NOT hallucinate

- Do NOT explain anything

- Return ONLY JSON

- If information is missing,
  return empty arrays

- A VC firm can belong to MULTIPLE sectors

- Extract ALL relevant sectors

----------------------------------------
FOCUS SECTOR TAXONOMY
----------------------------------------

Allowed focus_sectors:

- Artificial Intelligence
- Enterprise AI
- B2B SaaS
- Voice AI
- Fintech
- Healthcare
- Developer Tools
- AI Infrastructure

----------------------------------------
SECTOR MAPPING RULES
----------------------------------------

Map concepts carefully.

Examples:

Voice AI:
- voice agents
- conversational AI
- speech AI
- voice automation
- call center AI
- AI voice platforms

→ Voice AI

Enterprise AI:
- enterprise automation
- workflow automation
- enterprise software
- enterprise copilots
- AI productivity

→ Enterprise AI

B2B SaaS:
- SaaS
- enterprise SaaS
- cloud software
- software platform
- recurring software products

→ B2B SaaS

AI Infrastructure:
- LLM infrastructure
- AI infrastructure
- inference systems
- vector databases
- AI tooling
- foundation models

→ AI Infrastructure

Developer Tools:
- API platforms
- developer infrastructure
- coding tools
- software tooling

→ Developer Tools

----------------------------------------
INVESTMENT STAGE TAXONOMY
----------------------------------------

Allowed investment_stage values:

- Pre-Seed
- Seed
- Series A
- Series B
- Series C
- Growth Stage
- IPO Stage

Normalize stages into ONLY these values.

Examples:
- early-stage → Seed
- expansion stage → Growth Stage

----------------------------------------
PARTNER EXTRACTION
----------------------------------------

partners should contain:
- VC partners
- managing partners
- investment team members
- general partners

Do NOT include:
- startup founders
- portfolio founders
- article authors

----------------------------------------
WEBSITE CONTENT
----------------------------------------

{markdown_content[:12000]}
"""


    # =========================================
    # RETRY LOGIC
    # =========================================

    for attempt in range(3):

        try:

            response = client.chat.completions.create(

                model="llama-3.3-70b-versatile",

                temperature=0,

                messages=[

                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            output = (

                response
                .choices[0]
                .message
                .content
            )

            cleaned = (

                output
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

            return json.loads(cleaned)

        except Exception as error:

            print(

                f"Groq parsing attempt failed: "
                f"{error}"
            )

            time.sleep(2)


    # =========================================
    # FALLBACK RESPONSE
    # =========================================

    return {

        "firm": "",
        "website": "",
        "focus_sectors": [],
        "investment_stage": [],
        "partners": []
    }