"""Populate region geometries from Natural Earth 1:10m data."""

from alembic import op
import sqlalchemy as sa
from datetime import datetime
from typing import Optional
import geopandas as gpd
from geoalchemy2.shape import from_shape
from sqlalchemy import text

revision = "20251225_0002"
down_revision = "20251224_0001"
branch_labels = None
depends_on = None


# Natural Earth 1:10m data URLs
NATURAL_EARTH_COUNTRIES_URL = (
    "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/"
    "10m/cultural/ne_10m_admin_0_countries.zip"
)
NATURAL_EARTH_STATES_URL = (
    "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/"
    "10m/cultural/ne_10m_admin_1_states_provinces.zip"
)


def normalize_name(name: str) -> str:
    """Normalize name for fuzzy matching."""
    if not name:
        return ""
    return name.lower().strip().replace(".", "").replace("-", " ")


def download_and_parse_shapefile(url: str, description: str) -> gpd.GeoDataFrame:
    """Download and parse a Natural Earth shapefile."""
    print(f"Downloading {description} from Natural Earth...")
    try:
        gdf = gpd.read_file(url)
        print(f"✓ Loaded {len(gdf)} {description} features")
        return gdf
    except Exception as e:
        raise RuntimeError(
            f"Failed to download {description} from {url}: {e}"
        ) from e


def populate_country_geometries(conn) -> tuple[int, int, list]:
    """Populate country geometries from Natural Earth data.

    Returns: (matched_count, total_count, unmatched_list)
    """
    print("\n=== Populating Country Geometries ===")

    # Download and parse Natural Earth countries
    countries_gdf = download_and_parse_shapefile(
        NATURAL_EARTH_COUNTRIES_URL,
        "countries"
    )

    # Get existing countries from database
    result = conn.execute(text("SELECT id, iso2, iso3, name FROM regions_country"))
    db_countries = {row[0]: {"iso2": row[1], "iso3": row[2], "name": row[3]}
                    for row in result}

    matched_count = 0
    unmatched = []

    print(f"Processing {len(countries_gdf)} Natural Earth countries...")

    for idx, row in countries_gdf.iterrows():
        ne_iso2 = str(row.get("ISO_A2", "")).upper().strip()
        ne_iso3 = str(row.get("ISO_A3", "")).upper().strip()
        ne_name = str(row.get("NAME", "")).strip()
        geometry = row.geometry

        # Skip invalid ISO codes
        if ne_iso2 in ["-99", ""] or ne_iso3 in ["-99", ""]:
            unmatched.append(f"{ne_name} (invalid ISO codes)")
            continue

        # Find matching database country
        matched_id = None
        for db_id, db_data in db_countries.items():
            if db_data["iso2"].upper() == ne_iso2 or db_data["iso3"].upper() == ne_iso3:
                matched_id = db_id
                break

        if matched_id:
            # Convert geometry to WKB
            geom_wkb = from_shape(geometry, srid=4326)

            # Update database
            conn.execute(
                text("""
                    UPDATE regions_country
                    SET geom = :geom, updated_at = :updated_at
                    WHERE id = :id
                """),
                {"geom": str(geom_wkb), "updated_at": datetime.utcnow(), "id": matched_id}
            )
            matched_count += 1

            if matched_count % 10 == 0:
                print(f"  Updated {matched_count} countries...")
        else:
            unmatched.append(f"{ne_name} ({ne_iso2}/{ne_iso3})")

    print(f"\n✓ Country Summary:")
    print(f"  Matched: {matched_count}")
    print(f"  Unmatched: {len(unmatched)}")

    if unmatched and len(unmatched) <= 20:
        print(f"  Unmatched countries: {', '.join(unmatched[:20])}")

    return matched_count, len(countries_gdf), unmatched


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

