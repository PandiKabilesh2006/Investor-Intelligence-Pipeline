import json
import os
import random

PARSED_FOLDER = "parsed_json"
os.makedirs(PARSED_FOLDER, exist_ok=True)

# Taxonomies used in the app
sectors = ["B2B SaaS", "Artificial Intelligence", "Voice AI", "Fintech", "Developer Tools", "DeepTech"]
stages = ["Seed", "Pre-Seed", "Series A", "Series B", "Growth Stage"]
geographies = ["United States", "India", "Europe", "Southeast Asia", "Middle East", "Global"]
firms = [
    "Alpha Capital", "Beta Ventures", "Gamma Fund", "Delta Partners", "Apex VC", "Summit Capital", 
    "Blue Horizon", "Redwood Ventures", "Horizon Equity", "Cascade Partners", "Prism Venture", "Synergy Capital",
    "Nexus Venture Partners", "Accel Partners", "Sequoia Capital", "Elevation Capital", "Lightspeed India",
    "Matrix Partners", "Kalaari Capital", "Chiratae Ventures", "3one4 Capital", "Blume Ventures",
    "Y Combinator", "Techstars", "500 Global", "Founders Fund", "Benchmark", "Greylock", "Andreessen Horowitz"
]
partner_names = [
    "Aarav Mehta", "Ananya Rao", "Arjun Kapoor", "Isha Menon", "Kavya Shah",
    "Neha Iyer", "Rahul Nair", "Rohan Gupta", "Sanjay Patel", "Vikram Singh",
    "Aisha Khan", "Daniel Lee", "Emily Chen", "Laura Smith", "Michael Johnson",
    "Priya Desai", "Ravi Narayan", "Sara Williams", "Thomas Brown", "Maya Reddy"
]

print("Generating mock investor JSON files...")

generated_count = 0
for i in range(1, 111):
    firm_name = f"{random.choice(firms)} {random.randint(100, 999)}"
    
    # Simple logic to avoid duplicate mock names
    safe_filename = firm_name.lower().replace(" ", "_")
    filename = os.path.join(PARSED_FOLDER, f"https___mock_investor_{safe_filename}.json")
    
    # Skip if file already exists
    if os.path.exists(filename):
        continue

    mock_investor = {
        "firm": firm_name,
        "website": f"https://www.{safe_filename.replace('_', '')}.com",
        "source_url": f"https://www.{safe_filename.replace('_', '')}.com/about",
        "focus_sectors": random.sample(sectors, k=random.randint(1, 3)),
        "investment_stage": random.sample(stages, k=random.randint(1, 2)),
        "geography": random.sample(geographies, k=random.randint(1, 2)),
        "contact_links": [f"https://twitter.com/{safe_filename.replace('_', '')}"],
        "partners": random.sample(partner_names, k=2),
        "portfolio_companies": [f"Startup {random.randint(1, 100)}", f"Startup {random.randint(101, 200)}"]
    }
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(mock_investor, f, indent=4, ensure_ascii=False)
    generated_count += 1

print(f"Successfully generated {generated_count} mock investor JSON files in {PARSED_FOLDER}.")
