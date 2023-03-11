import csv
import logging
import re
import sys
import urllib
import xml.etree.ElementTree as et
from typing import Optional, Tuple

import requests


class MediaServer:

    def __init__(self, ip: str, auth: Optional[Tuple[str, str]] = None, secure: bool = False):
        self.__ip = ip
        self.__auth = auth
        self.__secure = secure
        self.__base_url = f"http{'s' if secure else ''}://{ip}/MCWS/v1"
        self.__token = None

    def as_dict(self) -> dict:
        return {self.__ip: (self.__auth, self.__secure)}

    def __repr__(self):
        suffix = f" [{self.__auth[0]}]" if self.__auth else ' [Unauthenticated]'
        return f"{self.__ip}{suffix}"

    def authenticate(self) -> bool:
        self.__token = None
        url = f"{self.__base_url}/Authenticate"
        r = requests.get(url, auth=self.__auth, timeout=(1, 5))
        if r.status_code == 200:
            response = et.fromstring(r.content)
            if response:
                r_status = response.attrib.get('Status', None)
                if r_status == 'OK':
                    for item in response:
                        if item.attrib['Name'] == 'Token':
                            self.__token = item.text
        if self.connected:
            return True
        else:
            raise ValueError('Authentication failure', r.url, r.status_code, r.text)

    @property
    def connected(self) -> bool:
        return self.__token is not None

    def __auth_if_required(self):
        if not self.connected:
            self.authenticate()

    def search(self, film_name: str, exact: bool = False) -> dict:
        self.__auth_if_required()
        url = f"{self.__base_url}/Files/Search"
        if exact:
            film_name = f"[{film_name}]"
        params = urllib.parse.urlencode({
            'Action': 'json',
            'Fields': 'Filename,Name,Key,Borrowed',
            'Query': f'[Name]={film_name} [Media Type]=Video [Media Sub Type]=Movie'
        }, quote_via=urllib.parse.quote)
        r = requests.get(url, auth=self.__auth, timeout=(1, 5), params=params)
        match = None
        if r.status_code == 200:
            results = r.json()
            if results:
                if len(results) > 1:
                    if not exact:
                        match = self.search(film_name, exact=True)
                        if not match:
                            print(f"NO MATCH for \"{film_name}\", {len(results)} candidates", file=sys.stderr)
                else:
                    match = results[0]
            elif not exact:
                if ' ' in film_name:
                    self.search(film_name, exact=True)
                else:
                    print(f"NO MATCH for \"{film_name}\", 0 candidates", file=sys.stderr)
        else:
            print(f"Unexpected response {r}")
        return match

    def set_value(self, key: str, field: str, value: str):
        self.__auth_if_required()
        url = f"{self.__base_url}/File/SetInfo"
        r = requests.get(url, auth=self.__auth, timeout=(1, 5), params={'File': key, 'FileType': 'Key', 'Field': field, 'Value': value})
        if r.status_code == 200:
            response = et.fromstring(r.content)
            if response is not None:
                r_status = response.attrib.get('Status', None)
                if r_status == 'OK':
                    return True
        return False


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
