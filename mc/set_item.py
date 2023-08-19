import csv
import re
import sys

from mediaserver import MediaServer

# logging.basicConfig()
# logging.getLogger().setLevel(logging.DEBUG)
# requests_log = logging.getLogger("urllib3")
# requests_log.setLevel(logging.DEBUG)
# requests_log.propagate = True

if __name__ == '__main__':
    input_file = sys.argv[1]
    mc = MediaServer(sys.argv[2], (sys.argv[3], sys.argv[4]))
    with open(input_file, "r", encoding="utf8") as cinema_paradiso:
        reader = csv.DictReader(cinema_paradiso, delimiter="\t")
        for line in reader:
            year = line["YEAR"]
            name = line["FILM"].strip()
            m = re.search(r'(.*)( \(BLU-RAY.*\))', name)
            if m:
                name = m.group(1)
            match = mc.search(name)
            if match:
                is_borrowed = match.get('Borrowed', 0)
                print(f"FOUND,{match['Key']},\"{match['Filename']}\",\"{name}\",{is_borrowed}")
                if not is_borrowed:
                    if not mc.set_value(match['Key'], 'Borrowed', '1'):
                        print(f"***FAILED TO SET VALUE***", file=sys.stderr)
