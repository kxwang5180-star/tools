import os
import tempfile
import unittest

import contact_cache


class ContactCacheTests(unittest.TestCase):
    def test_cache_indexes_name_employee_no_and_email_to_user_id(self):
        cache = contact_cache.build_contact_cache(
            [
                {
                    "name": "王康旭",
                    "user_id": "12139762",
                    "open_id": "ou_test",
                    "email": "person@example.com",
                    "employee_no": "E001",
                }
            ]
        )

        self.assertEqual(contact_cache.resolve_receive_id(cache, "王康旭", "user_id"), "12139762")
        self.assertEqual(contact_cache.resolve_receive_id(cache, "E001", "user_id"), "12139762")
        self.assertEqual(contact_cache.resolve_receive_id(cache, "person@example.com", "open_id"), "ou_test")

    def test_cache_round_trips_as_json(self):
        cache = contact_cache.build_contact_cache(
            [{"name": "王康旭", "user_id": "12139762", "employee_no": "E001"}]
        )

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            path = temp_file.name
        try:
            contact_cache.save_cache(cache, path)
            loaded = contact_cache.load_cache(path)
        finally:
            os.unlink(path)

        self.assertEqual(contact_cache.resolve_receive_id(loaded, "王康旭", "user_id"), "12139762")


if __name__ == "__main__":
    unittest.main()
