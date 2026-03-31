"""
Queries the GitHub GraphQL API for the user's commit contributions
across all repositories (last 12 months) and updates the README.md
section between <!-- TOP_CONTRIB_START --> and <!-- TOP_CONTRIB_END -->.
"""

import os
import re
import sys
import requests

TOKEN = os.environ["GH_TOKEN"]
USERNAME = os.environ.get("GH_USERNAME", "Lore09")
TOP_N = 5

HEADERS = {
    "Authorization": f"bearer {TOKEN}",
    "Content-Type": "application/json",
}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      commitContributionsByRepository(maxRepositories: 50) {
        repository {
          nameWithOwner
          url
          description
          primaryLanguage {
            name
          }
          isPrivate
        }
        contributions {
          totalCount
        }
      }
    }
  }
}
"""

MEDALS = ["🥇", "🥈", "🥉"]


def fetch_contributions():
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": QUERY, "variables": {"login": USERNAME}},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        print("GraphQL errors:", data["errors"], file=sys.stderr)
        sys.exit(1)

    contribs = (
        data["data"]["user"]["contributionsCollection"][
            "commitContributionsByRepository"
        ]
    )

    public = [c for c in contribs if not c["repository"]["isPrivate"]]
    public.sort(key=lambda x: x["contributions"]["totalCount"], reverse=True)
    return public[:TOP_N]


def make_row(rank, entry):
    repo = entry["repository"]
    count = entry["contributions"]["totalCount"]
    name_with_owner = repo["nameWithOwner"]
    owner, name = name_with_owner.split("/", 1)
    url = repo["url"]
    lang = (repo["primaryLanguage"] or {}).get("name", "")

    medal = MEDALS[rank] if rank < len(MEDALS) else str(rank + 1)

    # Show org/repo if it's not the user's own repo, otherwise just repo name
    display = f"`{owner}/`**[{name}]({url})**" if owner.lower() != USERNAME.lower() else f"**[{name}]({url})**"
    lang_str = f"`{lang}`" if lang else ""

    return f"| {medal} | {display} | {lang_str} | {count} |"


def build_table(repos):
    header = "| | Repository | Language | Commits |\n|:---:|:---|:---:|:---:|"
    rows = [make_row(i, entry) for i, entry in enumerate(repos)]
    return "\n".join([header] + rows)


def update_readme(table):
    readme_path = "README.md"
    with open(readme_path, "r") as f:
        content = f.read()

    replacement = f"<!-- TOP_CONTRIB_START -->\n{table}\n<!-- TOP_CONTRIB_END -->"

    new_content, n = re.subn(
        r"<!-- TOP_CONTRIB_START -->.*?<!-- TOP_CONTRIB_END -->",
        replacement,
        content,
        flags=re.DOTALL,
    )

    if n == 0:
        print("ERROR: markers not found in README.md", file=sys.stderr)
        sys.exit(1)

    with open(readme_path, "w") as f:
        f.write(new_content)

    print(f"Updated {n} section(s).")


if __name__ == "__main__":
    repos = fetch_contributions()
    if not repos:
        print("No public contributions found, skipping update.")
        sys.exit(0)
    table = build_table(repos)
    update_readme(table)
    for i, entry in enumerate(repos):
        r = entry["repository"]
        print(f"  {MEDALS[i] if i < 3 else i+1} {r['nameWithOwner']}: {entry['contributions']['totalCount']} commits")
