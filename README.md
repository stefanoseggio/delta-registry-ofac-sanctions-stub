# OFAC Maritime Sanctions Sample Puller (free, one-off)

This is a free, open-source, one-off sample puller for the US Treasury OFAC
Specially Designated Nationals (SDN) list, filtered down to vessel-type
entries (`sdnType = Vessel`). It runs once, does a single unauthenticated
`GET` against OFAC's own public SDN.XML feed
(`https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML`),
parses out up to 20 vessel records, and writes them to a local JSON file so
you can see the real shape of the data before deciding whether you need
something more. There's no scheduling, no state between runs, and no
retry logic - it's a plain local script you run from your own machine
whenever you want a fresh look.

## Setup & run

```bash
pip install -r requirements.txt
python main.py
```

This prints progress to stdout and writes `ofac_vessel_sample.json` in the
current directory. Each run is independent - there's no database, no
key-value store, and nothing persisted between invocations.

## Example output

A real record from a live run of this script (`ofac_vessel_sample.json`),
field names match the vessel record shape OFAC's own feed exposes:

```json
{
  "uid": "4243",
  "vesselName": "EBANO",
  "sdnType": "Vessel",
  "programs": ["CUBA"],
  "imoNumber": "7406784",
  "mmsi": null,
  "callSign": null,
  "vesselType": "General Cargo",
  "vesselFlag": "Panama",
  "tonnage": "2595",
  "grossRegisteredTonnage": "1865",
  "vesselOwner": null,
  "source_url": "https://sanctionssearch.ofac.treas.gov/Details.aspx?id=4243",
  "fetched_at": "2026-09-10T14:58:22.893045+00:00"
}
```

`imoNumber` and `mmsi` come back `null` when OFAC hasn't recorded that
identifier for a given vessel - that's a real, documented gap in OFAC's own
data, not a bug in this script (not every SDN vessel entry carries an IMO or
MMSI number).

## What this doesn't do

This script is deliberately simple. It does **not**:

- **Schedule itself.** It runs once when you invoke it and exits. There's no
  cron, no polling loop, no recurring trigger.
- **Track changes (delta detection) between runs.** Every run is a cold
  start - it has no memory of what it fetched last time, so it can't tell you
  what's new, what changed, or what was delisted since your last pull.
- **Retry failed requests.** If the HTTP request fails, the script prints the
  error and exits. There's no exponential backoff, no re-attempt on a 429 or
  503, and no handling for a request that times out partway.
- **Cross-reference the UN Security Council Consolidated Sanctions List**, or
  provide any independent corroboration of an OFAC designation by IMO number.
- **Hold a dead-letter queue.** A malformed record or a parse failure isn't
  captured anywhere for later inspection - it just stops the run.
- **Cap at more than a small sample.** This script hard-caps at 20 records
  even though the live feed carries roughly 1,540 vessel-type SDN entries at
  any given time; it's meant as a look at the data shape, not a full extract.

For scheduled runs, delta/change-tracking, and reliability guarantees, see
the production actor:
https://apify.com/stefano_seggio/actor-19-maritime-sanctions-monitor

That actor also cross-references each vessel's IMO number against the UN
Security Council Consolidated Sanctions List, retries both source feeds with
exponential backoff, and classifies every record as a new sanction, a
sanctions-program change, an unrelated field update, or a delisting - all on
pay-per-event pricing ($0.0005 per delivered record, plus a small one-time
actor-start charge).
