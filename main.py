"""
main.py - Free, one-off OFAC vessel-sanctions sample puller.

Fetches the live US Treasury OFAC Specially Designated Nationals (SDN) list,
filters it down to vessel-type entries, and saves a small local JSON sample.

This is a single run against a single source. It does NOT schedule itself,
track changes between runs, retry failed requests, or hold a dead-letter
queue for failures -- see README.md, "What this doesn't do", for the honest
list of gaps and where the paid, hosted actor picks up.

Source: US Treasury OFAC Specially Designated Nationals (SDN) list, the same
public, unauthenticated XML feed used by the production actor
(stefano_seggio/actor-19-maritime-sanctions-monitor).
"""

import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

# Same live feed URL the production actor fetches. A bare unauthenticated GET
# returns an HTTP redirect to a pre-signed storage URL; requests follows
# redirects by default, so no special handling is needed here.
OFAC_SDN_XML_URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML"

# OFAC's own public per-record lookup tool, used to build a human-readable
# source link for each vessel in the sample output.
OFAC_DETAILS_BASE_URL = "https://sanctionssearch.ofac.treas.gov/Details.aspx"

# The live SDN.XML feed declares this default namespace on its <sdnList> root.
SDN_NAMESPACE = {"sdn": "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/XML"}

MAX_RECORDS = 20
OUTPUT_FILE = "ofac_vessel_sample.json"
REQUEST_TIMEOUT_SECONDS = 60


def fetch_sdn_xml(url):
    """Single, one-off HTTP GET. No retry, no backoff -- if this fails, the
    run stops and prints why. See README.md for what the paid actor adds."""
    response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def child_text(element, tag_name):
    """Returns the stripped text of a direct namespaced child, or None."""
    child = element.find(f"sdn:{tag_name}", SDN_NAMESPACE)
    if child is not None and child.text:
        return child.text.strip()
    return None


def extract_imo_and_mmsi(entry):
    """Walks idList/id looking for the IMO ship number and MMSI, mirroring
    how the production actor's parser reads the same idList block."""
    imo_number = None
    mmsi = None
    for id_el in entry.findall("sdn:idList/sdn:id", SDN_NAMESPACE):
        id_type = child_text(id_el, "idType")
        id_number = child_text(id_el, "idNumber")
        if not id_type or not id_number:
            continue
        if id_type == "Vessel Registration Identification":
            digits = "".join(ch for ch in id_number if ch.isdigit())
            if len(digits) == 7:
                imo_number = digits
        elif id_type == "MMSI":
            mmsi = id_number
    return imo_number, mmsi


def extract_vessel_records(xml_text, limit):
    root = ET.fromstring(xml_text)
    records = []

    for entry in root.findall("sdn:sdnEntry", SDN_NAMESPACE):
        sdn_type = child_text(entry, "sdnType")
        if sdn_type != "Vessel":
            continue

        uid = child_text(entry, "uid")
        vessel_name = child_text(entry, "lastName")
        if not uid or not vessel_name:
            continue

        programs = [
            program.text.strip()
            for program in entry.findall("sdn:programList/sdn:program", SDN_NAMESPACE)
            if program.text
        ]

        imo_number, mmsi = extract_imo_and_mmsi(entry)

        vessel_info = entry.find("sdn:vesselInfo", SDN_NAMESPACE)
        vessel_type = child_text(vessel_info, "vesselType") if vessel_info is not None else None
        vessel_flag = child_text(vessel_info, "vesselFlag") if vessel_info is not None else None
        call_sign = child_text(vessel_info, "callSign") if vessel_info is not None else None
        tonnage = child_text(vessel_info, "tonnage") if vessel_info is not None else None
        gross_registered_tonnage = (
            child_text(vessel_info, "grossRegisteredTonnage") if vessel_info is not None else None
        )
        vessel_owner = child_text(vessel_info, "vesselOwner") if vessel_info is not None else None

        records.append(
            {
                "uid": uid,
                "vesselName": vessel_name,
                "sdnType": sdn_type,
                "programs": programs,
                "imoNumber": imo_number,
                "mmsi": mmsi,
                "callSign": call_sign,
                "vesselType": vessel_type,
                "vesselFlag": vessel_flag,
                "tonnage": tonnage,
                "grossRegisteredTonnage": gross_registered_tonnage,
                "vesselOwner": vessel_owner,
                "source_url": f"{OFAC_DETAILS_BASE_URL}?id={uid}",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        if len(records) >= limit:
            break

    return records


def main():
    print(f"Fetching {OFAC_SDN_XML_URL} ...")
    try:
        xml_text = fetch_sdn_xml(OFAC_SDN_XML_URL)
    except requests.exceptions.RequestException as error:
        # Real error handling, deliberately without retry/backoff -- a single
        # failed fetch just fails this run. The paid actor retries with
        # exponential backoff instead; see README.md.
        print(f"ERROR: failed to fetch OFAC SDN list: {error}")
        sys.exit(1)

    try:
        records = extract_vessel_records(xml_text, MAX_RECORDS)
    except ET.ParseError as error:
        print(f"ERROR: failed to parse OFAC SDN XML: {error}")
        sys.exit(1)

    print(f"Parsed {len(records)} vessel-type SDN record(s) (capped at {MAX_RECORDS}).")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"Saved sample to {OUTPUT_FILE}")
    if records:
        print("First record:")
        print(json.dumps(records[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
