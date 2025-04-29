import os
import JoplinClient as JoplinClient
import argparse
# Create Joplin client - it will automatically read the token from .env
joplin = JoplinClient.JoplinClient()

# Or you can provide the token directly
# joplin = JoplinClient(token="your_token_here")

parser = argparse.ArgumentParser()
parser.add_argument("--prefix", type=str, default=None)
# Get notebooks
notebooks = joplin.GetNotebook()
if notebooks and 'items' in notebooks:
    for notebook in notebooks['items']:
        print(f"Notebook: {notebook['title']} (ID: {notebook['id']})")
  #      if notebook and 'itmes' in notebook:
  #          for innnerNote in notebook['items']:
  #             print(f"Notebook: {notebook['title']} (ID: {notebook['id']})")




# Create a note
result = joplin.CreateNote(
    title="My Analysis Note",
    body="# Analysis Results\n\nHere are my findings...",
    parent_id=None  # Replace with notebook ID if needed
)


if result:
    print(f"Note created with ID: {result['id']}")


notebooks = joplin.GetNotebook()
if notebooks and 'items' in notebooks:
    for notebook in notebooks['items']:
        print(f"Notebook: {notebook['title']} (ID: {notebook['id']})")


