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

# contributionsCollection defaults to the last ~12 months.
# Increase maxRepositories to cast a wider net before filtering.
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
          isFork
        }
        contributions {
          totalCount
        }
      }
    }
  }
}
"""

# Map common language names to shields.io logo slugs
LANG_LOGO = {
    "Python": "python",
    "JavaScript": "javascript",
    "TypeScript": "typescript",
    "Go": "go",
    "Rust": "rust",
    "Java": "openjdk",
    "C": "c",
    "C++": "cplusplus",
    "Shell": "gnubash",
    "Dockerfile": "docker",
    "HCL": "terraform",
}

LANG_COLOR = {
    "Python": "3776AB",
    "JavaScript": "F7DF1E",
    "TypeScript": "3178C6",
    "Go": "00ADD8",
    "Rust": "DEA584",
    "Java": "ED8B00",
    "C": "00599C",
    "C++": "00599C",
    "Shell": "4EAA25",
    "Dockerfile": "2496ED",
    "HCL": "7B42BC",
}


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

    # Keep only public repos (forks included — you contribute to OSS too)
    public = [c for c in contribs if not c["repository"]["isPrivate"]]
    public.sort(key=lambda x: x["contributions"]["totalCount"], reverse=True)
    return public[:TOP_N]


def shields_escape(text):
    """Escape text for shields.io badge URL segments."""
    return text.replace("-", "--").replace("_", "__").replace(" ", "_")


def make_badge(entry):
    repo = entry["repository"]
    count = entry["contributions"]["totalCount"]
    name = repo["nameWithOwner"].split("/")[-1]
    url = repo["url"]
    lang = (repo["primaryLanguage"] or {}).get("name", "")

    logo = LANG_LOGO.get(lang, "github")
    color = LANG_COLOR.get(lang, "F75C7E")

    label = shields_escape(name)
    message = shields_escape(f"{count} commits")

    badge_url = (
        f"https://img.shields.io/badge/{label}-{message}-{color}"
        f"?style=for-the-badge&logo={logo}&logoColor=white"
    )
    return f"[![{name}]({badge_url})]({url})"


def update_readme(badges):
    readme_path = "README.md"
    with open(readme_path, "r") as f:
        content = f.read()

    inner = "\n".join(badges)
    replacement = f"<!-- TOP_CONTRIB_START -->\n{inner}\n<!-- TOP_CONTRIB_END -->"

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

    print(f"Updated {n} section(s) with top {len(badges)} repos.")


if __name__ == "__main__":
    repos = fetch_contributions()
    if not repos:
        print("No public contributions found, skipping update.")
        sys.exit(0)
    badges = [make_badge(r) for r in repos]
    update_readme(badges)
    for entry in repos:
        r = entry["repository"]
        print(f"  {r['nameWithOwner']}: {entry['contributions']['totalCount']} commits")
