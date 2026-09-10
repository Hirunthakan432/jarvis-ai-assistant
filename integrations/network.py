"""Search results and read-only, configured LAN sensor endpoints."""
import ipaddress
import json
import time
from urllib.parse import urlsplit


def web_search(query):
    from ddgs import DDGS
    rows = DDGS(timeout=10).text(query, max_results=5)
    return [{'title': str(row.get('title', ''))[:300], 'url': row.get('href', ''),
             'snippet': str(row.get('body', ''))[:1500]} for row in rows
            if urlsplit(row.get('href', '')).scheme in {'http', 'https'}][:5]


def validate_device_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {'http', 'https'} or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Device endpoint must be an HTTP(S) URL without credentials or fragment.')
    address = ipaddress.ip_address(parsed.hostname or '')
    networks = [ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', 'fc00::/7')]
    if not any(address in net for net in networks):
        raise ValueError('Device endpoint must use a literal private LAN IP address.')
    return url


def read_device(name, devices):
    import requests
    if name not in devices:
        raise ValueError('Unknown device. Configure it in JARVIS_DEVICES_JSON first.')
    url = validate_device_url(devices[name])
    with requests.Session() as session:
        session.trust_env = False
        with session.get(url, timeout=(3, 5), allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise ValueError(f'Device returned HTTP {response.status_code}.')
            data = bytearray()
            deadline = time.monotonic() + 10
            for chunk in response.iter_content(1):
                if time.monotonic() > deadline:
                    raise ValueError("Device response took too long.")
                data.extend(chunk)
                if len(data) > 32768:
                    raise ValueError('Device response exceeds 32 KB.')
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError('Device must return a JSON object containing sensor readings.')
    return {'device': name, 'readings': value}
