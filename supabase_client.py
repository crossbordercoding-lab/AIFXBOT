"""
AIFXBOT Supabase Client
Uses the Supabase REST API directly via requests (no heavy SDK needed).
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

class SupabaseClient:
    def __init__(self, url: str = None, key: str = None):
        self.url = (url or SUPABASE_URL).rstrip("/")
        self.key = key or SUPABASE_KEY
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

    def _request(self, method: str, path: str, **kwargs):
        endpoint = f"{self.url}/rest/v1/{path.lstrip('/')}"
        resp = requests.request(method, endpoint, headers=self.headers, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.text else None

    def select(self, table: str, columns: str = "*", **filters):
        """Query rows from a table."""
        params = {"select": columns}
        params.update(filters)
        return self._request("GET", f"/{table}", params=params)

    def insert(self, table: str, data: dict or list):
        """Insert row(s)."""
        payload = data if isinstance(data, list) else [data]
        return self._request("POST", f"/{table}", json=payload)

    def update(self, table: str, data: dict, **filters):
        """Update rows matching filters."""
        return self._request("PATCH", f"/{table}", params=filters, json=data)

    def delete(self, table: str, **filters):
        """Delete rows matching filters."""
        return self._request("DELETE", f"/{table}", params=filters)

    def upsert(self, table: str, data: dict or list):
        """Upsert row(s)."""
        payload = data if isinstance(data, list) else [data]
        h = self.headers.copy()
        h["Prefer"] = "resolution=merge-duplicates,return=representation"
        return self._request("POST", f"/{table}", headers=h, json=payload)

def test_connection():
    """Test that Supabase is reachable and the key is valid."""
    client = SupabaseClient()
    try:
        # health-check via a lightweight system query
        r = requests.get(
            f"{client.url}/rest/v1/",
            headers={"apikey": client.key, "Authorization": f"Bearer {client.key}"}
        )
        r.raise_for_status()
        print(f"✅ Supabase connected! Status: {r.status_code}")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()
