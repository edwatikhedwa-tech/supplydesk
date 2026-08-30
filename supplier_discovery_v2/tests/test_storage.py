import tempfile
import unittest
from pathlib import Path

from supplier_discovery_v2.models import ContactCandidate, OfferCandidate, QueryVariant, SellerCandidate
from supplier_discovery_v2.storage import DiscoveryStore


class StorageTests(unittest.TestCase):
    def test_isolated_store_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "discovery.sqlite3"
            store = DiscoveryStore(path)
            store.create_run("r1", "r1", "live", [])
            seller = SellerCandidate("s1", "Test Supplier", "fixture", "https://supplier.example/product", "seller_offer", "exact_match", 0.9, [ContactCandidate("email", "sales@supplier.example", 0.9, "https://supplier.example/contact")], ["https://supplier.example/contact"], "qualified")
            offer = OfferCandidate("p1", "fixture", "https://supplier.example/product", "Cable", "buy", "seller_offer", "exact_match", 0.9, seller, seller.contacts, seller.evidence_urls, "qualified")
            store.add_offers("r1", [offer, offer])
            store.add_offers("r1", [offer])
            store.commit()
            count = store.connection.execute("SELECT COUNT(*) FROM offer_candidates").fetchone()[0]
            contacts = store.connection.execute("SELECT COUNT(*) FROM candidate_contacts").fetchone()[0]
            self.assertEqual(count, 1)
            self.assertEqual(contacts, 1)
            store.close()
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
