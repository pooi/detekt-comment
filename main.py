#!/usr/bin/env python3

import json
import sys
from xml.etree.ElementTree import parse

import requests
from bs4 import BeautifulSoup


def find_pull_request():
    response = requests.get(
        f"{github_api_url}/repos/{repository}/pulls",
        headers=api_headers
    )

    if response.ok:
        pull_requests = response.json()
        for pull_request in pull_requests:
            if pull_request["head"]["ref"] == branch:
                return pull_request["url"]
        return None
    else:
        print(f"FIND-PULL-REQUEST-ERROR, code={response.status_code}, body={response.json()}")
        return None


def get_pull_request_files():
    response = requests.get(
        f"{pull_request_url}/files?per_page=100",
        headers=api_headers
    )

    if response.ok:
        return response.json()
    else:
        print(f"GET-PULL-REQUEST-FILES-ERROR, code={response.status_code}, body={response.json()}")
        return []


def create_review_comment(comment):
    response = requests.post(
        f"{pull_request_url}/comments".replace("/pulls/", "/issues/"),
        headers=api_headers,
        json={
            'body': comment
        }
    )

    if response.ok:
        return response.json()
    else:
        print(f"CREATE-REVIEW-COMMENT-ERROR, code={response.status_code}, body={response.json()}")
        return None


def generate_table(result):
    text = "# Detekt Report - Failed\n"

    for name in result:
        if len(result[name]) > 0:
            text += f"## {name}\n"
            text += "|Source|Severity|Line|Message|\n"
            text += "|---|---|---|---|\n"
            for error in result[name]:
                text += f"|{error['source']}|{error['severity']}|{error['location']}|{error['message']}|\n"
            text += "\n\n"
    return text


def get_changed_files():
    return [file['filename'] for file in get_pull_request_files()]


def build_changed_files_result(root):
    changed_files = get_changed_files()
    print("\n".join(changed_files))

    detekt_result = dict()
    for file in root.findall("file"):
        name = file.attrib["name"]
        if name in detekt_result:
            file_result = detekt_result[name]
        else:
            file_result = []
            detekt_result[name] = file_result

        for error in file.findall("error"):
            file_result.append({
                "source": error.attrib["source"].replace("detekt.", ""),
                "severity": error.attrib["severity"],
                "message": error.attrib["message"],
                "location": f"{error.attrib['line']}:{error.attrib['column']}"
            })

    changed_file_result = {}
    for key in detekt_result:
        for changed_file in changed_files:
            if key.endswith(changed_file):
                changed_file_result[changed_file] = detekt_result[key]

    print(json.dumps(changed_file_result, indent=2))
    return changed_file_result


def read_success_html():
    page = open(html_path, "rt", encoding='utf-8').read()
    soup = BeautifulSoup(page, 'html.parser')

    body = soup.find('body')

    is_print = False
    body_text = "<h1>Detekt Report - Success</h1>\n"
    for tag in body.contents:
        str_tag = str(tag)
        if "Complexity Report" in str_tag or is_print:
            is_print = True
            body_text += str_tag

    return body_text


def main():
    tree = parse(xml_path)
    root = tree.getroot()

    result = build_changed_files_result(root)

    if len(result) > 0:
        comment = generate_table(result)
    else:
        comment = read_success_html()

    print(comment)
    create_review_comment(comment)


if __name__ == '__main__':
    if len(sys.argv) > 6:
        xml_path = sys.argv[1]
        html_path = sys.argv[2]
        github_token = sys.argv[3]

        api_headers = {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': f"token {github_token}"
        }

        github_api_url = sys.argv[4]
        repository = sys.argv[5]
        branch = sys.argv[6]
        branch = branch.split("/")[-1]

        if len(sys.argv) > 7:
            pull_request_url = sys.argv[7]
        else:
            pull_request_url = find_pull_request()

        if pull_request_url is None:
            print("CAN'T FIND PULL REQUEST")
            exit(0)
        else:
            print(pull_request_url)

        main()
    else:
        print("Invalid arguments")
