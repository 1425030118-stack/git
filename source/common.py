# -*- coding: utf-8 -*-
import json
import os
import requests
import time


def get_proxy_config():
    """Return proxy settings for local VPN / Clash / V2Ray style HTTP/SOCKS proxies."""
    proxy = (
        os.getenv('HTTPS_PROXY') or os.getenv('https_proxy') or
        os.getenv('HTTP_PROXY') or os.getenv('http_proxy') or
        'http://127.0.0.1:7897'
    )
    return {
        'http': proxy,
        'https': proxy,
    }


def get_access_token():
    with open('../access_token.txt', 'r') as f:
        access_token = f.read().strip()
    return access_token


def write_text(file_name, method, text):
    """
    write text to file
    method: 'a'-append, 'w'-overwrite
    """
    with open(file_name, method, encoding='utf-8') as f:
        f.write(text)


def write_ranking_repo(file_name, method, repos):
    # method: 'a'-append or 'w'-overwrite
    table_head = "| Ranking | Project Name | Stars | Forks | Language | Open Issues | Description | Last Commit |\n\
| ------- | ------------ | ----- | ----- | -------- | ----------- | ----------- | ----------- |\n"
    with open(file_name, method, encoding='utf-8') as f:
        f.write(table_head)
        for idx, repo in enumerate(repos):
            repo_description = repo['description']
            if repo_description is not None:
                repo_description = repo_description.replace('|', '\|')  # in case there is '|' in description
            f.write("| {} | [{}]({}) | {} | {} | {} | {} | {} | {} |\n".format(
                idx + 1, repo['name'], repo['html_url'], repo['stargazers_count'], repo['forks_count'],
                repo['language'], repo['open_issues_count'], repo_description, repo['pushed_at']
            ))
        f.write('\n')


def get_api_repos(API_URL):
    """
    get repos of api, return repos list
    """
    access_token = get_access_token()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.113 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Authorization': 'token {}'.format(access_token),
    }
    s = requests.session()
    s.keep_alive = False  # don't keep the session
    time.sleep(3)  # not get so fast
    proxies = get_proxy_config()
    # requests.packages.urllib3.disable_warnings() # disable InsecureRequestWarning of verify=False,
    r = requests.get(API_URL, headers=headers, proxies=proxies, timeout=30)
    if r.status_code != 200:
        raise ValueError('Can not retrieve from {}'.format(API_URL))
    repos_dict = json.loads(r.content)
    repos = repos_dict['items']
    return repos


def get_graphql_data(GQL):
    """
    Execute one GitHub GraphQL request, retrying only transient failures.
    """
    access_token = get_access_token()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.113 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Authorization': 'bearer {}'.format(access_token),
    }
    graphql_api = "https://api.github.com/graphql"
    proxies = get_proxy_config()
    with requests.Session() as session:
        for attempt in range(3):
            try:
                response = session.post(
                    url=graphql_api,
                    json={"query": GQL},
                    headers=headers,
                    proxies=proxies,
                    timeout=30,
                )
            except requests.RequestException as error:
                if attempt == 2:
                    raise RuntimeError(
                        f"GitHub GraphQL request failed after 3 attempts: {error}"
                    ) from error
                time.sleep(2 ** attempt)
                continue

            if response.status_code in (429, 500, 502, 503, 504):
                if attempt == 2:
                    raise RuntimeError(
                        "GitHub GraphQL request failed after 3 attempts "
                        f"with HTTP {response.status_code}: {response.text[:500]}"
                    )
                time.sleep(2 ** attempt)
                continue
            if response.status_code != 200:
                raise RuntimeError(
                    "GitHub GraphQL request failed with HTTP "
                    f"{response.status_code}: {response.text[:500]}"
                )
            return response.json()

    raise RuntimeError("GitHub GraphQL request failed without a response.")
