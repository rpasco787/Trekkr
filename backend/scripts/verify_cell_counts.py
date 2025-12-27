#!/usr/bin/env python3
"""Verify that cell counts were estimated correctly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func
from database import SessionLocal
from models.geo import CountryRegion, StateRegion


def verify_countries(db):
    """Verify country cell counts."""
    total = db.query(func.count(CountryRegion.id)).scalar()
    with_geom = db.query(func.count(CountryRegion.id)).filter(
        CountryRegion.geom.isnot(None)
    ).scalar()
    with_r6 = db.query(func.count(CountryRegion.id)).filter(
        CountryRegion.land_cells_total_resolution6.isnot(None)
    ).scalar()
    with_r8 = db.query(func.count(CountryRegion.id)).filter(
        CountryRegion.land_cells_total_resolution8.isnot(None)
    ).scalar()

    print("COUNTRIES:")
    print(f"  Total countries: {total}")
    print(f"  With geometries: {with_geom}")
    print(f"  With resolution 6 estimates: {with_r6}")
    print(f"  With resolution 8 estimates: {with_r8}")

    # Sample a few countries
    samples = db.query(CountryRegion).filter(
        CountryRegion.land_cells_total_resolution6.isnot(None)
    ).limit(5).all()

    print("\n  Sample countries:")
    for country in samples:
        print(f"    {country.name}: R6≈{country.land_cells_total_resolution6:,}, "
              f"R8≈{country.land_cells_total_resolution8:,}")

        # Sanity check: R8 should be larger than R6 (finer resolution)
        if country.land_cells_total_resolution8 <= country.land_cells_total_resolution6:
            print(f"      ⚠️  WARNING: R8 should be > R6")

    return with_geom == with_r6 == with_r8


def verify_states(db):
    """Verify state cell counts."""
    total = db.query(func.count(StateRegion.id)).scalar()
    with_geom = db.query(func.count(StateRegion.id)).filter(
        StateRegion.geom.isnot(None)
    ).scalar()
    with_r6 = db.query(func.count(StateRegion.id)).filter(
        StateRegion.land_cells_total_resolution6.isnot(None)
    ).scalar()
    with_r8 = db.query(func.count(StateRegion.id)).filter(
        StateRegion.land_cells_total_resolution8.isnot(None)
    ).scalar()

    print("\nSTATES/REGIONS:")
    print(f"  Total states: {total}")
    print(f"  With geometries: {with_geom}")
    print(f"  With resolution 6 estimates: {with_r6}")
    print(f"  With resolution 8 estimates: {with_r8}")

    # Sample a few states
    samples = db.query(StateRegion).filter(
        StateRegion.land_cells_total_resolution6.isnot(None)
    ).limit(5).all()

    print("\n  Sample states:")
    for state in samples:
        print(f"    {state.name}: R6≈{state.land_cells_total_resolution6:,}, "
              f"R8≈{state.land_cells_total_resolution8:,}")

        # Sanity check
        if state.land_cells_total_resolution8 <= state.land_cells_total_resolution6:
            print(f"      ⚠️  WARNING: R8 should be > R6")

    return with_geom == with_r6 == with_r8


def main():
    """Main verification."""
    db = SessionLocal()

    try:
        print("=" * 80)
        print("CELL COUNT VERIFICATION")
        print("=" * 80)
        print()

        countries_ok = verify_countries(db)
        states_ok = verify_states(db)

        print("\n" + "=" * 80)
        if countries_ok and states_ok:
            print("✅ VERIFICATION PASSED")
            print("All regions with geometries have cell count estimates populated.")
            sys.exit(0)
        else:
            print("❌ VERIFICATION FAILED")
            print("Some regions are missing cell count estimates.")
            sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
