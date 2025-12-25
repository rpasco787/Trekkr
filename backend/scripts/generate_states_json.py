#!/usr/bin/env python3
"""Generate states.json from ISO 3166-2 subdivision data using pycountry.

This is a one-time script to extract ISO 3166-2 subdivisions and create
the states.json data file for seeding the regions_state table.

Usage:
    pip install pycountry
    python scripts/generate_states_json.py
"""

import json
from pathlib import Path

import pycountry


def load_countries_json():
    """Load country data from the bundled JSON file."""
    data_dir = Path(__file__).parent.parent / "data"
    countries_file = data_dir / "countries.json"

    if not countries_file.exists():
        raise FileNotFoundError(f"Countries data file not found: {countries_file}")

    with open(countries_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_subdivisions_for_country(iso2: str) -> list[dict]:
    """Get all ISO 3166-2 subdivisions for a country.

    Args:
        iso2: Two-letter country code (e.g., 'US', 'GB')

    Returns:
        List of subdivision dicts with country_iso2, code, and name
    """
    subdivisions = []

    try:
        # pycountry.subdivisions.get() returns subdivisions for a country
        country_subdivisions = pycountry.subdivisions.get(country_code=iso2)

        if country_subdivisions:
            for sub in country_subdivisions:
                subdivisions.append({
                    "country_iso2": iso2,
                    "code": sub.code,  # Full ISO code like 'US-CA'
                    "name": sub.name,
                })
    except (KeyError, LookupError):
        # Country not found in pycountry or has no subdivisions
        pass

    return subdivisions


def generate_states_data():
    """Generate complete states data from all countries.

    For countries with ISO 3166-2 subdivisions, includes all subdivisions.
    For countries without subdivisions, creates a placeholder entry.
    """
    countries = load_countries_json()
    all_states = []
    countries_with_subs = 0
    countries_without_subs = 0

    print(f"Processing {len(countries)} countries...")

    for country in countries:
        iso2 = country["iso2"]
        name = country["name"]

        subdivisions = get_subdivisions_for_country(iso2)

        if subdivisions:
            all_states.extend(subdivisions)
            countries_with_subs += 1
            print(f"  {iso2} ({name}): {len(subdivisions)} subdivisions")
        else:
            # Create placeholder for countries without subdivisions
            placeholder = {
                "country_iso2": iso2,
                "code": f"{iso2}-00",
                "name": "National",
            }
            all_states.append(placeholder)
            countries_without_subs += 1
            print(f"  {iso2} ({name}): No subdivisions -> placeholder created")

    return all_states, countries_with_subs, countries_without_subs


def save_states_json(states: list[dict]):
    """Save states data to JSON file."""
    data_dir = Path(__file__).parent.parent / "data"
    states_file = data_dir / "states.json"

    with open(states_file, "w", encoding="utf-8") as f:
        json.dump(states, f, indent=2, ensure_ascii=False)

    return states_file


def main():
    print("=" * 60)
    print("ISO 3166-2 States/Subdivisions Generator")
    print("=" * 60)
    print()

    # Generate the data
    states, with_subs, without_subs = generate_states_data()

    print()
    print("-" * 60)
    print("Summary:")
    print(f"  Countries with subdivisions: {with_subs}")
    print(f"  Countries without subdivisions (placeholders): {without_subs}")
    print(f"  Total state/subdivision entries: {len(states)}")
    print()

    # Save to JSON
    output_path = save_states_json(states)
    print(f"Data saved to: {output_path}")
    print()

    # Show some examples
    print("Sample entries:")
    for state in states[:5]:
        print(f"  {state['code']}: {state['name']} ({state['country_iso2']})")
    print("  ...")


if __name__ == "__main__":
    main()