# -*- coding: utf-8 -*-
import csv
from datetime import datetime, timezone
import os
from common import get_graphql_data

CSV_COLUMNS = [
    'rank', 'item', 'repo_name', 'stars', 'forks', 'language', 'repo_url', 'username',
    'issues', 'last_commit', 'description',
]


class ProcessorGQL(object):
    """
    Github GraphQL API v4
    ref: https://docs.github.com/en/graphql
    use graphql to get data, limit 5000 points per hour
    check rate_limit with :
    curl -H "Authorization: bearer your-access-token" -X POST -d "{\"query\": \"{ rateLimit { limit cost remaining resetAt used }}\" }" https://api.github.com/graphql
    """

    def __init__(self):
        self.gql_stars = """query {
    search(query: "stars:>1000 sort:stars", type: REPOSITORY, first:100) {
                edges {
                    node {
                        ...on Repository {
                            name
                            url
                            stargazerCount
                            owner {
                                login
                            }
                            description
                            pushedAt
                        }
                    }
                }
            }
        }
        """

    @staticmethod
    def parse_gql_result(result):
        if result.get("errors"):
            messages = "; ".join(error.get("message", "Unknown GraphQL error")
                                 for error in result["errors"])
            raise ValueError(f"GitHub GraphQL query failed: {messages}")
        try:
            edges = result["data"]["search"]["edges"]
        except (KeyError, TypeError) as error:
            raise ValueError("GitHub returned an unexpected Stars ranking response.") from error

        res = []
        for repo in edges:
            repo_data = repo['node']
            res.append({
                'name': repo_data['name'],
                'stargazers_count': repo_data['stargazerCount'],
                'forks_count': '',
                'language': '',
                'html_url': repo_data['url'],
                'owner': {
                    'login': repo_data['owner']['login'],
                },
                'open_issues_count': '',
                'pushed_at': repo_data['pushedAt'],
                'description': repo_data['description']
            })
        return res

    def get_top_stars(self):
        print("Fetching GitHub Stars Top 100 (one GraphQL request)...")
        repos = self.parse_gql_result(get_graphql_data(self.gql_stars))
        if not repos:
            raise ValueError("GitHub returned an empty Stars ranking.")
        print(f"Fetched {len(repos)} repositories.")
        return repos


class WriteFile(object):
    def __init__(self, repos_stars):
        self.repos_stars = repos_stars
        self.rows = [
            {
                'rank': index,
                'item': 'top-100-stars',
                'repo_name': repo['name'],
                'stars': repo['stargazers_count'],
                'forks': repo['forks_count'],
                'language': repo['language'],
                'repo_url': repo['html_url'],
                'username': repo['owner']['login'],
                'issues': repo['open_issues_count'],
                'last_commit': repo['pushed_at'],
                'description': repo['description'] or '',
            }
            for index, repo in enumerate(repos_stars, start=1)
        ]

    @staticmethod
    def _markdown_table(repos):
        lines = [
            "| Ranking | Project Name | Stars | Description | Last Commit |",
            "| ------- | ------------ | ----- | ----------- | ----------- |",
        ]
        for index, repo in enumerate(repos, start=1):
            description = (repo.get('description') or '').replace('|', r'\|').replace('\n', ' ')
            lines.append(
                f"| {index} | [{repo['name']}]({repo['html_url']}) | "
                f"{repo['stargazers_count']} | {description} | {repo['pushed_at']} |"
            )
        return '\n'.join(lines) + '\n'

    def write_readme(self):
        write_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        readme = f"""[Github Ranking](./README.md)
==========

**A list of GitHub repositories ranked by stars.**

*Last Automatic Update Time: {write_time}*

## Sponsor me

[Buy Me a Coffee | Alipay & WeChat Pay](https://afdian.com/a/EvanLi/plan)

[afdian 爱发电 EvanLi | 支付宝/微信支付](https://afdian.com/a/EvanLi/plan)

## Most Stars

This is top 10, for more click **[Top 100 Stars](Top100/Top-100-stars.md)**

{self._markdown_table(self.repos_stars[:10])}"""
        with open("../README.md", "w", encoding="utf-8", newline="") as readme_file:
            readme_file.write(readme)

    def write_top100(self):
        os.makedirs("../Top100", exist_ok=True)
        top100_path = "../Top100/Top-100-stars.md"
        with open(top100_path, "w", encoding="utf-8", newline="") as ranking_file:
            ranking_file.write(
                "[Github Ranking](../README.md)\n==========\n\n## Top 100 Stars\n\n"
            )
            ranking_file.write(self._markdown_table(self.repos_stars))
        print("Saved Stars Top 100 to Top100/Top-100-stars.md")

    def save_to_csv(self):
        save_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        os.makedirs('../Data', exist_ok=True)
        csv_path = f"../Data/github-ranking-{save_date}.csv"
        with open(csv_path, "w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(self.rows)
        print(f"Saved {len(self.rows)} Stars entries to Data/github-ranking-{save_date}.csv")


def run_by_gql():
    ROOT_PATH = os.path.abspath(os.path.join(__file__, "../../"))
    os.chdir(os.path.join(ROOT_PATH, 'source'))

    processor = ProcessorGQL()
    repos_stars = processor.get_top_stars()
    wt_obj = WriteFile(repos_stars)
    wt_obj.write_readme()
    wt_obj.write_top100()
    wt_obj.save_to_csv()


if __name__ == "__main__":
    t1 = datetime.now()
    run_by_gql()
    print("Total time: {}s".format((datetime.now() - t1).total_seconds()))
