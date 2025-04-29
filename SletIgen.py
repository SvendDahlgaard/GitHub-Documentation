from pathlib import Path
import argparse
import JoplinClient

parser = argparse.ArgumentParser()
parser.add_argument("--SummaryDirectory", type = str, required = True)
parser.add_argument("--NoteBookName", type = str, default = "Test")
args = parser.parse_args()

directory = Path(f"analysis/{args.SummaryDirectory}")
MarkDownFiles = list(directory.glob("*.md"))

for file in MarkDownFiles:
    print(file)

path = Path("analysis\SvendDahlgaard_databricks-sdk-py\miscellaneous.md")
contet = path.read_text(encoding='utf-8')


joplin = JoplinClient.JoplinClient()
joplin.CreateNote(title="test", body=contet)
print("file uploaded")



