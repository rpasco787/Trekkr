"""Map service for retrieving user's visited areas."""

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


class MapService:
    """Service for map-related queries."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def get_summary(self) -> dict:
        """Get all countries and regions the user has visited.

        Returns:
            dict with 'countries' and 'regions' lists
        """
        # Query distinct countries
        countries_query = text("""
            SELECT DISTINCT rc.iso2 AS code, rc.name
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_country rc ON hc.country_id = rc.id
            WHERE ucv.user_id = :user_id
            ORDER BY rc.name
        """)
        countries_result = self.db.execute(
            countries_query, {"user_id": self.user_id}
        ).fetchall()

        countries = [
            {"code": row.code, "name": row.name}
            for row in countries_result
        ]

        # Query distinct regions
        regions_query = text("""
            SELECT DISTINCT
                CONCAT(rc.iso2, '-', rs.code) AS code,
                rs.name
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_state rs ON hc.state_id = rs.id
            JOIN regions_country rc ON rs.country_id = rc.id
            WHERE ucv.user_id = :user_id
            ORDER BY rs.name
        """)
        regions_result = self.db.execute(
            regions_query, {"user_id": self.user_id}
        ).fetchall()

        regions = [
            {"code": row.code, "name": row.name}
            for row in regions_result
        ]

        return {"countries": countries, "regions": regions}

    def get_cells_in_viewport(
        self,
        min_lng: float,
        min_lat: float,
        max_lng: float,
        max_lat: float,
        limit: Optional[int] = None,
    ) -> dict:
        """Get H3 cell indexes within the bounding box.

        Args:
            min_lng: Western longitude bound
            min_lat: Southern latitude bound
            max_lng: Eastern longitude bound
            max_lat: Northern latitude bound
            limit: Optional maximum number of cells to return (for future use)

        Returns:
            dict with 'res6' and 'res8' lists of H3 index strings
        """
        query = text("""
            SELECT hc.h3_index, hc.res
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            WHERE ucv.user_id = :user_id
              AND hc.res IN (6, 8)
              AND ST_Intersects(
                  hc.centroid::geometry,
                  ST_MakeEnvelope(:min_lng, :min_lat, :max_lng, :max_lat, 4326)
              )
            ORDER BY hc.h3_index
        """)

        result = self.db.execute(query, {
            "user_id": self.user_id,
            "min_lng": min_lng,
            "min_lat": min_lat,
            "max_lng": max_lng,
            "max_lat": max_lat,
        }).fetchall()

        res6, res8 = [], []
        for row in result:
            if row.res == 6:
                res6.append(row.h3_index)
            else:
                res8.append(row.h3_index)

        return {"res6": res6, "res8": res8}
