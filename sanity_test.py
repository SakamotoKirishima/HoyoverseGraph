import os
print("NOTION_TOKEN exists:", "NOTION_TOKEN" in os.environ)
print("All env keys:", list(os.environ.keys())[:10])