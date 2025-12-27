#!/usr/bin/env python3
"""Compute H3 cell count estimates using area-based calculation.

Estimates cell counts by dividing region area by average cell area:
  estimated_cells = ST_Area(geom, use_spheroid=true) / average_hexagon_area(resolution)

This provides fast approximations suitable for user statistics.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import h3
from sqlalchemy import text

from database import SessionLocal


def get_average_cell_area(resolution: int) -> float:
    """Get average hexagon area in square meters for given H3 resolution.

    Args:
        resolution: H3 resolution level (0-15)

    Returns:
        Average cell area in square meters
    """
    # h3.average_hexagon_area returns area in km² by default
    area_km2 = h3.average_hexagon_area(resolution, unit='km^2')
    area_m2 = area_km2 * 1_000_000  # Convert to square meters
    return area_m2


def estimate_cell_count_for_region(db, table_name: str, region_id: int, resolution: int) -> int:
    """Estimate H3 cell count for a region using area-based calculation.

    Args:
        db: Database session
        table_name: Name of table (regions_country or regions_state)
        region_id: ID of the region
        resolution: H3 resolution level

    Returns:
        Estimated number of H3 cells covering the region
    """
    # Get region area in square meters using PostGIS
    # ST_Area(geom, use_spheroid=true) gives accurate area on Earth's surface
    query = text(f"""
        SELECT ST_Area(geom::geography) as area_m2
        FROM {table_name}
        WHERE id = :region_id AND geom IS NOT NULL
    """)

    result = db.execute(query, {"region_id": region_id}).fetchone()

    if not result or result.area_m2 is None:
        return 0

    area_m2 = float(result.area_m2)

    # Get average cell area for this resolution
    avg_cell_area = get_average_cell_area(resolution)

    # Estimate cell count
    estimated_cells = int(round(area_m2 / avg_cell_area))

    return max(estimated_cells, 1)  # At least 1 cell if region has area


def compute_country_cells(db):
    """Estimate and update cell counts for all countries."""
    # Get all countries with geometries
    query = text("""
        SELECT id, name, iso3
        FROM regions_country
        WHERE geom IS NOT NULL
        ORDER BY name
    """)

    countries = db.execute(query).fetchall()

    print(f"\nProcessing {len(countries)} countries...")

    # Get average cell areas once (same for all countries)
    avg_area_r6 = get_average_cell_area(6)
    avg_area_r8 = get_average_cell_area(8)

    print(f"Average cell area at resolution 6: {avg_area_r6:,.0f} m²")
    print(f"Average cell area at resolution 8: {avg_area_r8:,.0f} m²")

    for i, country in enumerate(countries, 1):
        country_id, name, iso3 = country
        print(f"[{i}/{len(countries)}] {name} ({iso3})")

        # Estimate cell counts at both resolutions
        cells_r6 = estimate_cell_count_for_region(db, "regions_country", country_id, 6)
        cells_r8 = estimate_cell_count_for_region(db, "regions_country", country_id, 8)

        print(f"  Resolution 6: ~{cells_r6:,} cells")
        print(f"  Resolution 8: ~{cells_r8:,} cells")

        # Update database
        update_query = text("""
            UPDATE regions_country
            SET land_cells_total_resolution6 = :cells_r6,
                land_cells_total_resolution8 = :cells_r8
            WHERE id = :country_id
        """)

        db.execute(update_query, {
            "cells_r6": cells_r6,
            "cells_r8": cells_r8,
            "country_id": country_id
        })

        # Periodic commits every 50 countries
        if i % 50 == 0:
            db.commit()
            print(f"  💾 Checkpoint: committed {i} countries")

    db.commit()
    print(f"\n✅ Updated {len(countries)} countries")


def compute_state_cells(db):
    """Estimate and update cell counts for all states."""
    # Get all states with geometries
    query = text("""
        SELECT s.id, s.name, c.name as country_name
        FROM regions_state s
        LEFT JOIN regions_country c ON s.country_id = c.id
        WHERE s.geom IS NOT NULL
        ORDER BY c.name, s.name
    """)

    states = db.execute(query).fetchall()

    print(f"\nProcessing {len(states)} states/regions...")

    # Get average cell areas once
    avg_area_r6 = get_average_cell_area(6)
    avg_area_r8 = get_average_cell_area(8)

    for i, state in enumerate(states, 1):
        state_id, name, country_name = state
        country_name = country_name or "Unknown"
        print(f"[{i}/{len(states)}] {name}, {country_name}")

        # Estimate cell counts at both resolutions
        cells_r6 = estimate_cell_count_for_region(db, "regions_state", state_id, 6)
        cells_r8 = estimate_cell_count_for_region(db, "regions_state", state_id, 8)

        print(f"  Resolution 6: ~{cells_r6:,} cells")
        print(f"  Resolution 8: ~{cells_r8:,} cells")

        # Update database
        update_query = text("""
            UPDATE regions_state
            SET land_cells_total_resolution6 = :cells_r6,
                land_cells_total_resolution8 = :cells_r8
            WHERE id = :state_id
        """)

        db.execute(update_query, {
            "cells_r6": cells_r6,
            "cells_r8": cells_r8,
            "state_id": state_id
        })

        # Periodic commits every 50 states
        if i % 50 == 0:
            db.commit()
            print(f"  💾 Checkpoint: committed {i} states")

    db.commit()
    print(f"\n✅ Updated {len(states)} states/regions")


def main():
    """Main execution."""
    db = SessionLocal()

    try:
        print("=" * 80)
        print("H3 CELL COUNT ESTIMATION (AREA-BASED)")
        print("=" * 80)

        # Compute for countries
        compute_country_cells(db)

        # Compute for states
        compute_state_cells(db)

        print("\n" + "=" * 80)
        print("✅ ESTIMATION COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
