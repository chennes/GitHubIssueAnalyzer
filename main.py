# SPDX-License-Identifier: GPL-3.0-or-later

# Copyright (c) 2025 Chris Hennes

""" This script loads an issue database from GitHub and converts it to a CSV file: it's designed purely for simple
 statistics generation, so doesn't pull all information, just title, dates, and labels. """

import json
import os
import time
from datetime import date
from typing import Dict, Optional
import csv

import requests

# CONFIGURATION
github_access_token = os.getenv("GITHUB_ACCESS_TOKEN")
start_date = date(2024, 1, 1)
end_date = date(2024, 12, 31)
community = "FreeCAD"
project = "FreeCAD"
endpoint = "https://api.github.com/graphql"
outfile = "C:\\Users\\chenn\\Desktop\\FreeCAD_Issues_Report.csv"
max_pages: Optional[int] = None


class IssueStatsWriter:
    query_base = """query GetIssueDates($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    issues(first: 100, after: $cursor) {
      edges {
        node {
          number
          title
          createdAt
          updatedAt
          closedAt
          state
          stateReason
          labels(first: 10) {
            edges {
              node {
                name
              }
            }
          }
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
  rateLimit {
    limit
    cost
    remaining
    resetAt
  }
}"""

    def __init__(self, owner: str, repo: str, output_file: str):
        """ Owner is the organization that owns the repo (the first component of a GitHub URL after its base) and
         repo is the name of the individual repo in that organization. All collected data will be processed into a
         CSV file named output_file. """
        if not github_access_token:
            raise RuntimeError("Could not get GitHub access token, check your environment")
        self.variables = {"owner": owner,
                          "repo": repo,
                          "cursor": None}
        if os.path.exists(output_file):
            result = input(f"This will overwrite the existing datafile at {outfile}. Continue [y/N]?")
            if result.lower() != "y":
                raise RuntimeError("Operation cancelled by user")
        self.output_file = output_file
        self.output_handle = open(self.output_file, "w", newline="", encoding="utf-8")
        self.writer = csv.writer(self.output_handle, dialect="excel")
        self.writer.writerow(["number",
                              "title",
                              "createdAt",
                              "updatedAt",
                              "closedAt",
                              "state",
                              "stateReason",
                              "labels"])

    def __del__(self):
        if hasattr(self, "output_handle"):
            self.output_handle.close()

    def total_issues(self) -> int:
        query = """query IssuesTotal($owner: String!, $repo: String!) {
  repository(owner: $owner, name: $repo) {
    issues {
      totalCount
    }
  }
}"""
        headers = {
            "Authorization": f"Bearer {github_access_token}"
        }
        result = requests.post(endpoint, json={"query": query, "variables": self.variables},
                               headers=headers, timeout=5)
        if result.status_code != 200:
            print(f"Failed to read GitHub issue data (Response code: {result.status_code})")
            return 0
        return result.json()["data"]["repository"]["issues"]["totalCount"]

    def run(self):
        """ Runs the GraphQL queries to generate the data set, pausing one second after each query unless the rate
         limiter is hit, in which case it will pause for one hour before attempting to continue. """
        more_pages = True
        counter = 0
        while more_pages:
            counter += 1
            print(f"Fetching data set {counter}...", end="")
            result = self._get_next_dataset()
            try:
                self._process_result(result)
            except KeyError as err:
                print(json.dumps(result, indent="  "))
                print(err)
                raise
            remaining = result["data"]["rateLimit"]["remaining"]
            print(f"fetch complete. ({remaining} queries remain before rate limit hit)")
            if remaining <= 0:
                print("Rate limit hit, pausing operation for an hour...")
                time.sleep(60 * 60)
            more_pages = result["data"]["repository"]["issues"]["pageInfo"]["hasNextPage"]
            if max_pages and counter >= max_pages:
                print("Page limit reached... stopping operation.")
                break
            if more_pages:
                time.sleep(1.0)  # Wait a second to help avoid rate limiters
        print("All data processed.")

    def _get_next_dataset(self) -> Dict:
        headers = {
            "Authorization": f"Bearer {github_access_token}"
        }
        result = requests.post(endpoint, json={"query": self.query_base, "variables": self.variables},
                               headers=headers, timeout=5)
        if result.status_code != 200:
            print(f"Failed to read GitHub issue data for {community}/{project} (Response code: {result.status_code})")
            return {}
        return result.json()

    def _process_result(self, result):
        """Reformat the data from the result object into the columnar data we want to store, and append it to the CSV
        file we're creating."""
        if result["data"]["repository"]["issues"]["pageInfo"]["hasNextPage"]:
            self.variables["cursor"] = result["data"]["repository"]["issues"]["pageInfo"]["endCursor"]
        issues = result["data"]["repository"]["issues"]["edges"]
        for issue in issues:
            labels = self._extract_labels(issue["node"])
            self.writer.writerow([issue["node"]["number"],
                                  issue["node"]["title"],
                                  issue["node"]["createdAt"],
                                  issue["node"]["updatedAt"],
                                  issue["node"]["closedAt"],
                                  issue["node"]["state"],
                                  issue["node"]["stateReason"],
                                  labels
                                  ])

    @staticmethod
    def _extract_labels(node: Dict) -> str:
        """Loop over the labels results and turn them into a single comma-separated list. This assumes that no label
        has a comma in it (and strips them if they do"""
        list_result = []
        for label in node["labels"]["edges"]:
            if "node" in label:
                list_result.append(label["node"]["name"].replace(",", " "))
        return ",".join(list_result)


if __name__ == "__main__":
    print(f"Getting the GitHub Issue statistics for {community}/{project}")
    print("This is a long process due to the potential for very large data sets and the presence of rate limiters")
    stats_writer = IssueStatsWriter(community, project, outfile)
    total_issues = stats_writer.total_issues()
    print(f"There are {total_issues} total issues, and they will be fetched in batches of 100.")
    stats_writer.run()
