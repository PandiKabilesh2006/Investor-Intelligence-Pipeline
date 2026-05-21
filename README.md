Investor Intelligence Pipeline

An AI-powered investor discovery and intelligence platform that combines web scraping, NLP, vector embeddings, semantic search, and LLM-powered insights to help startups discover the right investors faster.

🚀 Overview

The Investor Intelligence Pipeline is an end-to-end intelligent system designed to:

Scrape investor and venture capital data from the web
Extract structured investment intelligence
Generate semantic vector embeddings
Store investor profiles in PostgreSQL + pgvector
Perform AI-powered semantic investor search
Support LLM-enhanced investor discovery workflows

The system enables founders, analysts, and startup teams to search investors using natural language queries such as:

“Seed-stage AI SaaS investors focused on B2B automation in India”

instead of relying only on filters or keyword matching.

✨ Core Features
🔍 AI-Powered Semantic Investor Search

Search investors using natural language.

Examples:

“Fintech investors in India”
“AI healthcare VCs investing in early-stage startups”
“SaaS investors focused on enterprise automation”

Uses:

Vector embeddings
pgvector similarity search
Semantic retrieval
🌐 Web Scraping Pipeline

Automatically collects investor intelligence from:

VC websites
Funding blogs
Investor directories
Startup ecosystems
Public investment databases

Supports scalable scraping workflows.

🧠 LLM-Based Information Extraction

Uses Large Language Models to extract:

Investor name
Firm name
Investment sectors
Funding stages
Geographic focus
Portfolio companies
Investment thesis
Website/contact links

Supports:

Groq API
Ollama fallback support
⚡ Groq + Ollama Fallback Architecture

High-performance LLM processing using:

Primary: Groq API
Fallback: Ollama local models

Benefits:

Reliability
Reduced downtime
Lower API dependency
Local inference support
🗄 PostgreSQL + pgvector Integration

Stores:

Structured investor metadata
Embedding vectors
Semantic search indexes

Supports:

Cosine similarity search
Fast vector retrieval
Scalable AI search infrastructure
🔎 Hybrid Investor Intelligence System

Combines:

Structured filtering
Semantic vector similarity
NLP-based understanding

Allows highly relevant investor matching.

📄 Markdown Parsing & Document Processing

Processes:

Web pages
Markdown files
Investment articles
Funding reports

Transforms unstructured content into structured investor intelligence.

🧩 Modular Backend Architecture

Built with scalable modular architecture:

Scrapers
Embedding engine
Database layer
Search engine
API layer
LLM extraction services

Easy to extend and maintain.

⚙️ FastAPI Backend

Provides scalable API endpoints for:

Investor search
Semantic retrieval
Data ingestion
Embedding generation
Search filtering

Interactive API docs available through Swagger UI.

🏗 System Architecture
                ┌─────────────────────┐
                │   Web Sources       │
                │ VC Sites / Blogs    │
                └─────────┬───────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │   Web Scraping      │
                │ Firecrawl / Crawlers│
                └─────────┬───────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │  Markdown Parsing   │
                │  Content Cleaning   │
                └─────────┬───────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │ LLM Information     │
                │ Extraction Engine   │
                │ Groq + Ollama       │
                └─────────┬───────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │ Structured Investor │
                │ Intelligence Data   │
                └─────────┬───────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │ Embedding Generator │
                │ SentenceTransformers│
                └─────────┬───────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │ PostgreSQL +        │
                │ pgvector Database   │
                └─────────┬───────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │ Semantic Search API │
                │ FastAPI             │
                └─────────┬───────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │ User Search Queries │
                └─────────────────────┘
🧠 Semantic Search Workflow
User Query
   ↓
Text Embedding Generation
   ↓
Vector Similarity Search
   ↓
Relevant Investor Retrieval
   ↓
Ranked Investor Results
📂 Project Structure
investor-intelligence-pipeline/
│
├── app/
│   ├── api/
│   ├── database/
│   ├── embeddings/
│   ├── extraction/
│   ├── models/
│   ├── scraping/
│   ├── search/
│   └── services/
│
├── data/
├── markdown_files/
├── scripts/
├── requirements.txt
├── insert_into_db.py
├── generate_embeddings.py
├── main.py
└── README.md
🛠 Tech Stack
Backend
Python
FastAPI
Database
PostgreSQL
pgvector
AI / ML
SentenceTransformers
NLP
Semantic Search
Vector Embeddings
LLM Providers
Groq API
Ollama
Scraping
Firecrawl
Custom Crawlers
⚡ Installation
1. Clone Repository
git clone <repository-url>
cd investor-intelligence-pipeline
2. Create Virtual Environment
Windows
python -m venv venv
venv\Scripts\activate
Linux / Mac
python3 -m venv venv
source venv/bin/activate
3. Install Dependencies
pip install -r requirements.txt
🗄 Database Setup
Install PostgreSQL

Install PostgreSQL locally.

Install pgvector Extension

Inside PostgreSQL:

CREATE EXTENSION vector;
Configure Environment Variables

Create .env

DATABASE_URL=postgresql://username:password@localhost:5432/investor_db

GROQ_API_KEY=your_groq_api_key

OLLAMA_BASE_URL=http://localhost:11434
▶️ Running the Pipeline
Step 1 — Scrape Investor Data
py scrape_data.py
Step 2 — Extract Structured Intelligence
py extract_investors.py
Step 3 — Insert Into Database
py -m insert_into_db.py
Step 4 — Generate Embeddings
py generate_embeddings.py
Step 5 — Start FastAPI Server
uvicorn app.main:app --reload
📘 API Documentation

After running FastAPI:

http://127.0.0.1:8000/docs

Swagger UI provides interactive API testing.

🔍 Example Semantic Search Query
{
  "query": "AI SaaS investors investing in seed-stage startups"
}
📊 Example Use Cases
🚀 Startup Founder

Find relevant investors for fundraising.

📈 Venture Analyst

Analyze investor focus areas and trends.

🧠 AI Research

Experiment with semantic retrieval systems.

💼 Investment Intelligence Platforms

Use as backend infrastructure for VC discovery products.

🔒 Reliability Features
Fallback LLM Architecture

If Groq API fails:

Groq → Ollama Fallback

Ensures uninterrupted extraction pipeline.

📈 Scalability

Designed for:

Large-scale investor datasets
Distributed scraping
AI retrieval systems
Production semantic search
🔮 Future Enhancements
Hybrid Search (BM25 + Vector)
Investor Recommendation Engine
RAG-based Investor Chatbot
Multi-agent Research System
Real-time Funding News Tracking
Investor Email Discovery
Graph-based VC Relationship Mapping
Frontend Dashboard
Kubernetes Deployment
Redis Caching
Async Processing Pipelines
🧪 Example Workflow
1. Scrape VC websites
2. Parse markdown/articles
3. Extract investor intelligence using LLMs
4. Store structured data
5. Generate embeddings
6. Store vectors in pgvector
7. Run semantic investor search
8. Return ranked investor matches
🧠 Why Semantic Search?

Traditional keyword search fails for nuanced investor discovery.

Semantic search understands meaning.

Example:

Query:

“AI healthcare seed investors”

Can retrieve:

“Machine learning healthcare venture firms”
“Digital health AI-focused investors”

even without exact keyword matching.

📌 Key Highlights

✅ End-to-end AI investor discovery platform
✅ Semantic vector search
✅ PostgreSQL + pgvector integration
✅ LLM-powered extraction
✅ Groq + Ollama fallback system
✅ FastAPI backend
✅ Modular architecture
✅ Scalable infrastructure
✅ Production-ready foundation

🤝 Contributing

Contributions are welcome.

Possible areas:

Better extraction pipelines
Improved ranking algorithms
New scraping integrations
Frontend development
Search optimization
📜 License

MIT License

👨‍💻 Author

Pandi Kabilesh

Aspiring AI Engineer • Data Scientist • Machine Learning Engineer

⭐ Final Vision

The goal of this project is to build an intelligent infrastructure layer for startup fundraising and investor discovery using:

AI
Semantic Search
Vector Databases
LLMs
Scalable Data Pipelines

transforming raw web data into actionable investor intelligence.
