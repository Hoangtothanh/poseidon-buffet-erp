from django.db import migrations


def add_weather_columns(apps, schema_editor):
    """
    Thêm các cột yếu tố ngoại cảnh vào bảng AIDuDoanLuuLuong.
    Tên bảng PostgreSQL thực tế: ai_analytics_aidudoanluuluong
      (AIDuDoanLuuLuong → lowercase → aidudoanluuluong)
    Tương thích cả PostgreSQL lẫn SQLite.
    """
    vendor = schema_editor.connection.vendor

    # Tên bảng thực tế trong DB (Django tự sinh từ app_label + model_name.lower())
    table = "ai_analytics_aidudoanluuluong"

    if vendor == 'postgresql':
        columns_to_add = [
            ("nhiet_do",                  "DOUBLE PRECISION"),
            ("luong_mua",                 "DOUBLE PRECISION"),
            ("weather_code",              "INTEGER"),
            ("mo_ta_thoi_tiet",           "VARCHAR(100)"),
            ("weather_adjustment_factor", "DOUBLE PRECISION"),
            ("is_holiday",                "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("ten_su_kien",               "VARCHAR(200)"),
        ]
        with schema_editor.connection.cursor() as cursor:
            for col_name, col_type in columns_to_add:
                sql = (
                    f"ALTER TABLE {table} "
                    f"ADD COLUMN IF NOT EXISTS {col_name} {col_type};"
                )
                cursor.execute(sql)
                print(f"    ✅ PostgreSQL: ADD COLUMN IF NOT EXISTS {col_name}")

    else:
        # SQLite
        columns_to_add = [
            ("nhiet_do",                  "REAL"),
            ("luong_mua",                 "REAL"),
            ("weather_code",              "INTEGER"),
            ("mo_ta_thoi_tiet",           "VARCHAR(100)"),
            ("weather_adjustment_factor", "REAL"),
            ("is_holiday",                "BOOLEAN NOT NULL DEFAULT 0"),
            ("ten_su_kien",               "VARCHAR(200)"),
        ]
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(f"PRAGMA table_info({table});")
            existing_cols = {row[1] for row in cursor.fetchall()}
            for col_name, col_type in columns_to_add:
                if col_name not in existing_cols:
                    cursor.execute(
                        f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type};"
                    )
                    print(f"    ✅ SQLite: Thêm cột {col_name}")
                else:
                    print(f"    ⏭️  SQLite: Cột {col_name} đã tồn tại")


class Migration(migrations.Migration):
    """
    Bổ sung 7 trường yếu tố ngoại cảnh (thời tiết + ngày lễ)
    vào bảng AIDuDoanLuuLuong — tương thích PostgreSQL & SQLite.
    """

    dependencies = [
        ('ai_analytics', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            add_weather_columns,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
