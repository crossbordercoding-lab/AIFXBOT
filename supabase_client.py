"""
AIFXBOT Supabase Client
Uses the Supabase REST API directly via requests (no heavy SDK needed).
"""
import requests

# Hardcoded Supabase credentials for AIFXBOT project
SUPABASE_URL = "https://dbrgkbkrmxgstlkaigbw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRicmdrYmtybXhnc3Rsa2FpZ2J3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg5ODY1NjcsImV4cCI6MjA5NDU2MjU2N30.IfIaWSwuSR0hbLn3ZuZxIWFhJlOMHdMpX4q9jEXfZ3A"

class SupabaseClient:
    def __init__(self, url: str = SUPABASE_URL, key: str = SUPABASE_KEY):
        self.url = url.rstrip("/")
        self.key = key
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        print(f"[init] Supabase URL: {self.url}")
        print(f"[init] Key loaded: {'Yes' if self.key else 'No - MISSING!'}")

    def _request(self, method: str, path: str, **kwargs):
        endpoint = f"{self.url}/rest/v1/{path.lstrip('/')}"
        print(f"[request] {method} {endpoint}")
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
    print("=" * 50)
    print("Testing Supabase connection for AIFXBOT...")
    print("=" * 50)
    client = SupabaseClient()
    try:
        # Query the test table we just created
        result = client.select("test_connection", "*")
        print(f"✅ Supabase connected! Found {len(result)} row(s) in test_connection")
        print(f"   Data: {result}")
        print("=" * 50)
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection failed: {e}")
        print("=" * 50)
        return False

if __name__ == "__main__":
    test_connection()
