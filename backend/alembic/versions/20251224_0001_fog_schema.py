"""Initial Fog Explorer schema: regions, H3 cells, visits, stats, streaks, achievements."""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry


revision = "20251224_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table first (previously managed by init_db)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=True),
        sa.Column("app_version", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_devices_user_id", "devices", ["user_id"])

    op.create_table(
        "regions_country",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("iso2", sa.String(length=2), nullable=False),
        sa.Column("iso3", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("geom", Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=True),
        sa.Column("land_cells_total", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("iso2", name="uq_regions_country_iso2"),
        sa.UniqueConstraint("iso3", name="uq_regions_country_iso3"),
    )
    op.create_index("ix_regions_country_iso2", "regions_country", ["iso2"])
    op.create_index("ix_regions_country_iso3", "regions_country", ["iso3"])
    op.create_index("ix_regions_country_name", "regions_country", ["name"])
    op.create_index(
        "ix_regions_country_geom",
        "regions_country",
        ["geom"],
        postgresql_using="gist",
    )

    op.create_table(
        "regions_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("regions_country.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("geom", Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=True),
        sa.Column("land_cells_total", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("country_id", "code", name="uq_regions_state_code"),
    )
    op.create_index("ix_regions_state_country_id", "regions_state", ["country_id"])
    op.create_index("ix_regions_state_code", "regions_state", ["code"])
    op.create_index("ix_regions_state_name", "regions_state", ["name"])
    op.create_index(
        "ix_regions_state_geom",
        "regions_state",
        ["geom"],
        postgresql_using="gist",
    )

    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("criteria_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("code", name="uq_achievements_code"),
    )
    op.create_index("ix_achievements_code", "achievements", ["code"])

    op.create_table(
        "h3_cells",
        sa.Column("h3_index", sa.String(length=25), primary_key=True),
        sa.Column("res", sa.SmallInteger(), nullable=False),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("regions_country.id", ondelete="SET NULL"), nullable=True),
        sa.Column("state_id", sa.Integer(), sa.ForeignKey("regions_state.id", ondelete="SET NULL"), nullable=True),
        sa.Column("centroid", Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("first_visited_at", sa.DateTime(), nullable=True),
        sa.Column("last_visited_at", sa.DateTime(), nullable=True),
        sa.Column("visit_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_h3_cells_res", "h3_cells", ["res"])
    op.create_index("ix_h3_cells_country_id", "h3_cells", ["country_id"])
    op.create_index("ix_h3_cells_state_id", "h3_cells", ["state_id"])

    op.create_table(
        "user_achievements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("achievement_id", sa.Integer(), sa.ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )
    op.create_index("ix_user_achievements_user_id", "user_achievements", ["user_id"])
    op.create_index("ix_user_achievements_achievement_id", "user_achievements", ["achievement_id"])

    op.create_table(
        "user_cell_visits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("h3_index", sa.String(length=25), sa.ForeignKey("h3_cells.h3_index", ondelete="CASCADE"), nullable=False),
        sa.Column("res", sa.SmallInteger(), nullable=False),
        sa.Column("first_visited_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_visited_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("visit_count", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("user_id", "h3_index", name="uq_user_cell"),
    )
    op.create_index("ix_user_cell_visits_user_res", "user_cell_visits", ["user_id", "res"])
    op.create_index("ix_user_cell_visits_h3_index", "user_cell_visits", ["h3_index"])
    op.create_index("ix_user_cell_visits_user_id", "user_cell_visits", ["user_id"])

    op.create_table(
        "user_country_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("regions_country.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cells_visited", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coverage_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("first_visited_at", sa.DateTime(), nullable=True),
        sa.Column("last_visited_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "country_id", name="uq_user_country_stat"),
    )
    op.create_index("ix_user_country_stats_user_id", "user_country_stats", ["user_id"])
    op.create_index("ix_user_country_stats_country_id", "user_country_stats", ["country_id"])

    op.create_table(
        "user_state_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("state_id", sa.Integer(), sa.ForeignKey("regions_state.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cells_visited", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coverage_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("first_visited_at", sa.DateTime(), nullable=True),
        sa.Column("last_visited_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "state_id", name="uq_user_state_stat"),
    )
    op.create_index("ix_user_state_stats_user_id", "user_state_stats", ["user_id"])
    op.create_index("ix_user_state_stats_state_id", "user_state_stats", ["state_id"])

    op.create_table(
        "user_streaks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("current_streak_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("longest_streak_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_streak_start", sa.Date(), nullable=True),
        sa.Column("current_streak_end", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_user_streaks_user_id", "user_streaks", ["user_id"])

    op.create_table(
        "ingest_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("received_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("cells_count", sa.Integer(), nullable=False),
        sa.Column("res_min", sa.SmallInteger(), nullable=True),
        sa.Column("res_max", sa.SmallInteger(), nullable=True),
    )
    op.create_index("ix_ingest_batches_user_id", "ingest_batches", ["user_id"])
    op.create_index("ix_ingest_batches_device_id", "ingest_batches", ["device_id"])


def downgrade() -> None:
    op.drop_index("ix_ingest_batches_device_id", table_name="ingest_batches")
    op.drop_index("ix_ingest_batches_user_id", table_name="ingest_batches")
    op.drop_table("ingest_batches")

    op.drop_index("ix_user_streaks_user_id", table_name="user_streaks")
    op.drop_table("user_streaks")

    op.drop_index("ix_user_state_stats_state_id", table_name="user_state_stats")
    op.drop_index("ix_user_state_stats_user_id", table_name="user_state_stats")
    op.drop_table("user_state_stats")

    op.drop_index("ix_user_country_stats_country_id", table_name="user_country_stats")
    op.drop_index("ix_user_country_stats_user_id", table_name="user_country_stats")
    op.drop_table("user_country_stats")

    op.drop_index("ix_user_cell_visits_user_id", table_name="user_cell_visits")
    op.drop_index("ix_user_cell_visits_h3_index", table_name="user_cell_visits")
    op.drop_index("ix_user_cell_visits_user_res", table_name="user_cell_visits")
    op.drop_table("user_cell_visits")

    op.drop_index("ix_user_achievements_achievement_id", table_name="user_achievements")
    op.drop_index("ix_user_achievements_user_id", table_name="user_achievements")
    op.drop_table("user_achievements")

    op.drop_index("ix_h3_cells_state_id", table_name="h3_cells")
    op.drop_index("ix_h3_cells_country_id", table_name="h3_cells")
    op.drop_index("ix_h3_cells_res", table_name="h3_cells")
    op.drop_table("h3_cells")

    op.drop_index("ix_achievements_code", table_name="achievements")
    op.drop_table("achievements")

    op.drop_index("ix_regions_state_geom", table_name="regions_state")
    op.drop_index("ix_regions_state_name", table_name="regions_state")
    op.drop_index("ix_regions_state_code", table_name="regions_state")
    op.drop_index("ix_regions_state_country_id", table_name="regions_state")
    op.drop_table("regions_state")

    op.drop_index("ix_regions_country_geom", table_name="regions_country")
    op.drop_index("ix_regions_country_name", table_name="regions_country")
    op.drop_index("ix_regions_country_iso3", table_name="regions_country")
    op.drop_index("ix_regions_country_iso2", table_name="regions_country")
    op.drop_table("regions_country")

    op.drop_index("ix_devices_user_id", table_name="devices")
    op.drop_table("devices")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")

