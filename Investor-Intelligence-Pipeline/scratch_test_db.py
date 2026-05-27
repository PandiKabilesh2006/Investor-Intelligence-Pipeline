import os
import sys
import unittest
from datetime import datetime

# Enable mock database URL for testing if not set
os.environ["DATABASE_URL"] = "sqlite:///test_investors.db"

from app.database.connection import init_db, get_db_session, Base, get_engine
from app.database.operations import (
    save_investors_to_db,
    get_existing_domains_from_db,
    get_cached_investor_count,
    get_cached_investors_by_category
)

class TestDatabaseLayer(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Initialize the temporary SQLite database."""
        print("  [TEST] Initializing test database...")
        init_db()

    @classmethod
    def tearDownClass(cls):
        """Clean up the test database file."""
        print("  [TEST] Cleaning up test database...")
        engine = get_engine()
        if engine:
            engine.dispose()
        if os.path.exists("test_investors.db"):
            try:
                os.remove("test_investors.db")
            except Exception as e:
                print(f"Failed to remove test DB file: {e}")

    def test_01_insert_and_retrieve(self):
        """Test inserting a new investor and retrieving it back with all relationships intact."""
        category = "ai_machine_learning"
        mock_investor = {
            "firm": "Antigravity Ventures",
            "website": "https://antigravity.ai",
            "thesis": "We invest in high-performance AI agents and neural search models.",
            "focus_sectors": ["Artificial Intelligence", "DevTools", "SaaS"],
            "investment_stage": ["Pre-Seed", "Seed"],
            "geography": ["India", "Global"],
            "fund_number": "Fund III",
            "fund_size": "$50M",
            "active_status": "Active",
            "pitch_process": "Apply on our website or get a warm intro.",
            "confidence_score": 18,
            "partners": [
                {"name": "Alice Agent", "role": "General Partner", "linkedin_url": "https://linkedin.com/in/alice", "twitter_url": ""},
                {"name": "Bob Neural", "role": "Technical Partner", "linkedin_url": "", "twitter_url": "https://twitter.com/bob"}
            ],
            "portfolio_companies": ["Acme AI", "NeuralWidgets", "FastSearch"]
        }

        # Save to DB
        count = save_investors_to_db([mock_investor], category)
        self.assertEqual(count, 1, "Should successfully save 1 investor")

        # Check count
        db_count = get_cached_investor_count(category)
        self.assertEqual(db_count, 1, "Should have 1 investor in the database for this category")

        # Retrieve and verify details
        retrieved = get_cached_investors_by_category(category)
        self.assertEqual(len(retrieved), 1, "Should retrieve exactly 1 investor")
        
        inv = retrieved[0]
        self.assertEqual(inv["firm"], "Antigravity Ventures")
        self.assertEqual(inv["website"], "https://antigravity.ai")
        self.assertEqual(inv["confidence_score"], 18)
        self.assertEqual(len(inv["partners"]), 2)
        self.assertEqual(inv["partners"][0]["name"], "Alice Agent")
        self.assertEqual(inv["partners"][0]["role"], "General Partner")
        self.assertEqual(inv["partners"][1]["twitter_url"], "https://twitter.com/bob")
        self.assertEqual(len(inv["portfolio_companies"]), 3)
        self.assertIn("Acme AI", inv["portfolio_companies"])

    def test_02_upsert_logic(self):
        """Test that re-saving an investor updates their details without duplicating columns."""
        category = "ai_machine_learning"
        
        # Updated investor data (higher confidence, new partner, modified sector)
        updated_investor = {
            "firm": "Antigravity Ventures",
            "website": "https://antigravity.ai",
            "thesis": "We invest in high-performance AI agents.",
            "focus_sectors": ["AI", "Supercomputing"], # changed focus
            "investment_stage": ["Pre-Seed", "Seed"],
            "geography": ["India", "Global"],
            "fund_number": "Fund III",
            "fund_size": "$75M", # updated fund size
            "active_status": "Active",
            "pitch_process": "Warm intro preferred.",
            "confidence_score": 19, # updated confidence score
            "partners": [
                {"name": "Alice Agent", "role": "General Partner", "linkedin_url": "https://linkedin.com/in/alice", "twitter_url": ""},
                {"name": "Charlie Agent", "role": "Associate", "linkedin_url": "https://linkedin.com/in/charlie", "twitter_url": ""} # replaced Bob with Charlie
            ],
            "portfolio_companies": ["Acme AI", "NeuralWidgets", "FastSearch", "NewAIWidget"] # added a portfolio company
        }

        # Save to DB (this should trigger an update)
        count = save_investors_to_db([updated_investor], category)
        self.assertEqual(count, 1, "Should successfully upsert 1 investor")

        # Total count should still be 1 (no duplication)
        db_count = get_cached_investor_count(category)
        self.assertEqual(db_count, 1, "Database count should remain 1 after upserting")

        # Retrieve and verify updated details
        retrieved = get_cached_investors_by_category(category)
        inv = retrieved[0]
        self.assertEqual(inv["confidence_score"], 19, "Confidence score should be updated to 19")
        self.assertEqual(inv["fund_size"], "$75M", "Fund size should be updated to $75M")
        self.assertEqual(len(inv["partners"]), 2, "Should still have exactly 2 partners")
        
        partner_names = [p["name"] for p in inv["partners"]]
        self.assertIn("Charlie Agent", partner_names)
        self.assertNotIn("Bob Neural", partner_names, "Bob Neural should have been cleaned up and replaced")
        
        self.assertEqual(len(inv["portfolio_companies"]), 4, "Portfolio company list should expand to 4")
        self.assertIn("NewAIWidget", inv["portfolio_companies"])

    def test_03_domain_exclusion(self):
        """Test that get_existing_domains_from_db successfully retrieves all domain keys."""
        domains = get_existing_domains_from_db()
        self.assertIn("antigravity.ai", domains, "Cleaned domain 'antigravity.ai' should be returned in the exclusion set")

if __name__ == "__main__":
    unittest.main()
