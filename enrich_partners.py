import os
import json
import time
import psycopg2
from groq import Groq
from app.config.settings import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    GROQ_API_KEY,
    TAVILY_API_KEY
)
from app.search.tavily_search import search_investors

# Initialize Groq Client
groq_client = Groq(api_key=GROQ_API_KEY)

def enrich_partner_profile(name, firm):
    print(f"\nEnriching profile for: {name} at {firm}")
    
    # 1. Search Tavily for the partner's profiles
    query = f'"{name}" "{firm}" linkedin role'
    try:
        search_results = search_investors(query, max_pages=1)
        results = search_results.get("results", [])
    except Exception as e:
        print(f"Search failed for {name}: {e}")
        return None
        
    if not results:
        print(f"No search results found for {name}")
        return None
        
    # Compile snippets for the LLM
    snippets_text = ""
    for idx, r in enumerate(results, start=1):
        snippets_text += f"[{idx}] Title: {r.get('title')}\nURL: {r.get('url')}\nSnippet: {r.get('content')}\n\n"
        
    # 2. Call Groq LLM to extract structured details from search snippets
    prompt = f"""
You are a venture capital research assistant.
Given the following web search results for the person '{name}' associated with the firm '{firm}', extract their job title/role, LinkedIn profile URL, and Twitter/X profile URL.

----------------------------------------
SEARCH RESULTS:
----------------------------------------
{snippets_text}

----------------------------------------
RULES:
----------------------------------------
1. "role": Must be their professional title at {firm} (e.g. Partner, General Partner, Managing Partner, Venture Partner, Principal, Associate, Analyst, etc.). Default is "".
2. "linkedin_url": Must be their personal LinkedIn profile URL (should look like https://www.linkedin.com/in/username). Ignore company LinkedIn pages. Default is "".
3. "twitter_url": Must be their personal Twitter/X profile URL (should look like https://twitter.com/username or https://x.com/username). Default is "".
4. Return ONLY a valid JSON object matching the schema below. No markdown wrapping (like ```json), no extra explanations.

----------------------------------------
SCHEMA:
----------------------------------------
{{
  "role": "extracted_role",
  "linkedin_url": "extracted_linkedin_url",
  "twitter_url": "extracted_twitter_url"
}}
"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        output = response.choices[0].message.content.strip()
        parsed = json.loads(output)
        return parsed
    except Exception as e:
        print(f"LLM extraction failed for {name}: {e}")
        return None

def main():
    # Connect to PostgreSQL
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    cur = conn.cursor()
    
    try:
        # Fetch partners with empty/null linkedin_url
        cur.execute("""
            SELECT p.id, p.name, i.firm
            FROM partners p
            JOIN investors i ON p.investor_id = i.id
            WHERE p.linkedin_url IS NULL OR p.linkedin_url = ''
            ORDER BY p.id ASC
        """)
        
        partners = cur.fetchall()
        print(f"Found {len(partners)} partners to enrich.")
        
        success_count = 0
        
        # Limit to 5 at a time to prevent rate limits, can be adjusted
        limit = 10
        
        for idx, (p_id, name, firm) in enumerate(partners[:limit], start=1):
            profile = enrich_partner_profile(name, firm)
            
            if profile:
                role = profile.get("role", "").strip()
                linkedin_url = profile.get("linkedin_url", "").strip()
                twitter_url = profile.get("twitter_url", "").strip()
                
                print(f"Extracted -> Role: '{role}' | LinkedIn: '{linkedin_url}' | Twitter: '{twitter_url}'")
                
                # Update database
                cur.execute("""
                    UPDATE partners
                    SET role = %s,
                        linkedin_url = %s,
                        twitter_url = %s
                    WHERE id = %s
                """, (role, linkedin_url, twitter_url, p_id))
                
                conn.commit()
                success_count += 1
            else:
                print(f"Skipped {name}")
                
            # Rate limit protection
            time.sleep(2)
            
        print(f"\nSuccessfully enriched {success_count}/{min(len(partners), limit)} profiles in this run!")
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
