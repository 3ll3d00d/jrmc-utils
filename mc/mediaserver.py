import sys
import urllib
from typing import Optional, Tuple, List, Union
from xml.etree import ElementTree as et

import requests


class MediaServer:

    def __init__(self, ip: str, auth: Optional[Tuple[str, str]] = None, secure: bool = False):
        self.__ip = ip
        self.__auth = auth
        self.__secure = secure
        self.__base_url = f"http{'s' if secure else ''}://{ip}/MCWS/v1"
        self.__session = None
        self.__token = None

    def as_dict(self) -> dict:
        return {self.__ip: (self.__auth, self.__secure)}

    def __repr__(self):
        suffix = f" [{self.__auth[0]}]" if self.__auth else ' [Unauthenticated]'
        return f"{self.__ip}{suffix}"

    def authenticate(self) -> bool:
        self.__token = None
        url = f"{self.__base_url}/Authenticate"
        self.__session = requests.Session()
        self.__session.auth = self.__auth
        r = self.__session.get(url, timeout=(1, 5))
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

    def search_by_name(self, film_name: str, exact: bool = False) -> dict:
        match = None
        if exact:
            film_name = f"[{film_name}]"
        results = self.search(f'[Name]={film_name}', 'Filename,Name,Key,Borrowed')
        if len(results) > 1:
            if not exact:
                match = self.search(f'[Name]=[{film_name}]', 'Filename,Name,Key,Borrowed')
                if not match:
                    print(f"NO MATCH for \"{film_name}\", {len(results)} candidates", file=sys.stderr)
            else:
                match = results[0]
        elif not exact:
            if ' ' in film_name:
                self.search_by_name(film_name, exact=True)
            else:
                print(f"NO MATCH for \"{film_name}\", 0 candidates", file=sys.stderr)
        return match

    def search(self, src_query: str, fields: str) -> Optional[Union[dict, list]]:
        self.__auth_if_required()
        url = f"{self.__base_url}/Files/Search"
        params = urllib.parse.urlencode({
            'Action': 'json',
            'Fields': fields,
            'Query': f'{src_query} [Media Type]=Video [Media Sub Type]=Movie'
        }, quote_via=urllib.parse.quote)
        r = self.__session.get(url, auth=self.__auth, timeout=(1, 5), params=params)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"Unexpected response {r}")
            return None

    def set_value(self, key: str, field: str, value: str):
        self.__auth_if_required()
        url = f"{self.__base_url}/File/SetInfo"
        r = self.__session.get(url, auth=self.__auth, timeout=(1, 5), params={'File': key, 'FileType': 'Key', 'Field': field, 'Value': value})
        if r.status_code == 200:
            response = et.fromstring(r.content)
            if response is not None:
                r_status = response.attrib.get('Status', None)
                if r_status == 'OK':
                    return True
        return False

    def set_position(self, position: int):
        self.__auth_if_required()
        url = f"{self.__base_url}/Playback/Position"
        r = self.__session.get(url, auth=self.__auth, timeout=(1, 5), params={'Position': position})
        if r.status_code == 200:
            response = et.fromstring(r.content)
            if response is not None:
                r_status = response.attrib.get('Status', None)
                if r_status == 'OK':
                    return True
        return False

    def get_position(self) -> int:
        self.__auth_if_required()
        url = f"{self.__base_url}/Playback/Position"
        r = self.__session.get(url, auth=self.__auth, timeout=(1, 5))
        if r.status_code == 200:
            response = et.fromstring(r.content)
            if response is not None:
                r_status = response.attrib.get('Status', None)
                if r_status == 'OK':
                    for child in response:
                        if child.tag == 'Item' and child.attrib.get('Name', '') == 'Position':
                            return int(child.text)
        return -1
