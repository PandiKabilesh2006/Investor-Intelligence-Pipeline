import json
import time
import ollama


# =========================================
# OLLAMA MODEL
# =========================================

MODEL_NAME = "qwen2.5:7b"


# =========================================
# INVESTOR PARSER
# =========================================

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

Voice AI:
- voice agents
- conversational AI
- speech AI
- call center AI

→ Voice AI

Enterprise AI:
- workflow automation
- enterprise software
- enterprise copilots

→ Enterprise AI

B2B SaaS:
- SaaS
- cloud software
- recurring software

→ B2B SaaS

AI Infrastructure:
- LLM infrastructure
- vector databases
- inference systems

→ AI Infrastructure

Developer Tools:
- API platforms
- developer infrastructure
- coding tools

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

            response = ollama.chat(

                model=MODEL_NAME,

                messages=[

                    {
                        "role": "user",
                        "content": prompt
                    }
                ],

                options={

                    "temperature": 0
                }
            )


            output = (

                response["message"]["content"]
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

                f"Ollama parsing failed: "
                f"{error}"
            )

            time.sleep(2)


    # =========================================
    # FALLBACK
    # =========================================

    return {

        "firm": "",
        "website": "",
        "focus_sectors": [],
        "investment_stage": [],
        "partners": []
    }