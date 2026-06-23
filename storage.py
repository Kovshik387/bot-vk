import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Patient:
    id: int
    full_name: str
    birth_date: str
    policy_number: str
    snils: str
    program: str
    active_until: str
    is_active: bool


class DmsStorage:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

    def initialize(self):
        self._create_schema()
        self._seed_demo_data()

    def close(self):
        self.connection.close()

    def _create_schema(self):
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                birth_date TEXT NOT NULL,
                policy_number TEXT NOT NULL UNIQUE,
                snils TEXT NOT NULL,
                program TEXT NOT NULL,
                active_until TEXT NOT NULL,
                is_active INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                access_type TEXT NOT NULL,
                description TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS clinics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                phone TEXT NOT NULL,
                work_time TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS clinic_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clinic_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                FOREIGN KEY (clinic_id) REFERENCES clinics(id),
                FOREIGN KEY (service_id) REFERENCES services(id),
                UNIQUE (clinic_id, service_id)
            );

            CREATE TABLE IF NOT EXISTS user_links (
                vk_user_id INTEGER PRIMARY KEY,
                patient_id INTEGER NOT NULL,
                linked_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            );

            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_user_id INTEGER NOT NULL,
                patient_id INTEGER,
                service_id INTEGER,
                clinic_id INTEGER,
                request_type TEXT NOT NULL,
                contact TEXT NOT NULL,
                preferred_time TEXT NOT NULL,
                comment TEXT NOT NULL,
                status TEXT NOT NULL,
                patient_instruction TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(id),
                FOREIGN KEY (service_id) REFERENCES services(id),
                FOREIGN KEY (clinic_id) REFERENCES clinics(id)
            );
            """
        )
        self.connection.commit()
        self._ensure_clinic_services_id()
        self._ensure_column("requests", "patient_instruction", "TEXT NOT NULL DEFAULT ''")
        self._ensure_requests_patient_nullable()

    def _ensure_clinic_services_id(self):
        columns = self.connection.execute("PRAGMA table_info(clinic_services)").fetchall()
        if any(column["name"] == "id" for column in columns):
            return

        self.connection.executescript(
            """
            CREATE TABLE clinic_services_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clinic_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                FOREIGN KEY (clinic_id) REFERENCES clinics(id),
                FOREIGN KEY (service_id) REFERENCES services(id),
                UNIQUE (clinic_id, service_id)
            );
            INSERT INTO clinic_services_new (clinic_id, service_id)
            SELECT clinic_id, service_id FROM clinic_services;
            DROP TABLE clinic_services;
            ALTER TABLE clinic_services_new RENAME TO clinic_services;
            """
        )
        self.connection.commit()

    def _ensure_column(self, table_name: str, column_name: str, definition: str):
        columns = self.connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        if any(column["name"] == column_name for column in columns):
            return
        self.connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
        self.connection.commit()

    def _ensure_requests_patient_nullable(self):
        columns = self.connection.execute("PRAGMA table_info(requests)").fetchall()
        patient_column = next((column for column in columns if column["name"] == "patient_id"), None)
        if not patient_column or patient_column["notnull"] == 0:
            return

        self.connection.executescript(
            """
            CREATE TABLE requests_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_user_id INTEGER NOT NULL,
                patient_id INTEGER,
                service_id INTEGER,
                clinic_id INTEGER,
                request_type TEXT NOT NULL,
                contact TEXT NOT NULL,
                preferred_time TEXT NOT NULL,
                comment TEXT NOT NULL,
                status TEXT NOT NULL,
                patient_instruction TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(id),
                FOREIGN KEY (service_id) REFERENCES services(id),
                FOREIGN KEY (clinic_id) REFERENCES clinics(id)
            );
            INSERT INTO requests_new (
                id, vk_user_id, patient_id, service_id, clinic_id, request_type,
                contact, preferred_time, comment, status, patient_instruction, created_at, updated_at
            )
            SELECT
                id, vk_user_id, patient_id, service_id, clinic_id, request_type,
                contact, preferred_time, comment, status,
                COALESCE(patient_instruction, ''),
                created_at, updated_at
            FROM requests;
            DROP TABLE requests;
            ALTER TABLE requests_new RENAME TO requests;
            """
        )
        self.connection.commit()

    def _seed_demo_data(self):
        cur = self.connection.execute("SELECT COUNT(*) AS total FROM patients")
        if cur.fetchone()["total"]:
            return

        patients = [
            ("Иванов Иван Иванович", "01.03.1990", "DMS-001-2026", "123-456-789 00", "Стандарт", "31.12.2026", 1),
            ("Петрова Анна Сергеевна", "15.08.1988", "DMS-002-2026", "987-654-321 00", "Расширенная", "31.12.2026", 1),
            ("Сидоров Павел Олегович", "22.11.1979", "DMS-003-2025", "111-222-333 44", "Стандарт", "31.12.2025", 0),
        ]
        self.connection.executemany(
            """
            INSERT INTO patients (full_name, birth_date, policy_number, snils, program, active_until, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            patients,
        )

        services = [
            ("Терапевт", "doctor", "direct", "Первичный прием терапевта доступен по прямому обращению."),
            ("Невролог", "doctor", "approval", "Прием узкого специалиста требует согласования со страховой компанией."),
            ("Кардиолог", "doctor", "approval", "Прием кардиолога оформляется после подтверждения страховой компании."),
            ("Общий анализ крови", "lab", "direct", "Базовый лабораторный анализ доступен по прямому обращению."),
            ("Биохимический анализ крови", "lab", "direct", "Лабораторное исследование доступно в партнерских организациях."),
            ("МРТ", "diagnostic", "approval", "Высокотехнологичная диагностика требует предварительного согласования."),
            ("УЗИ", "diagnostic", "approval", "Диагностическое исследование требует проверки условий программы ДМС."),
        ]
        self.connection.executemany(
            "INSERT INTO services (name, category, access_type, description) VALUES (?, ?, ?, ?)",
            services,
        )

        clinics = [
            ("Медцентр Здоровье", "г. Воронеж, ул. Плехановская, 45", "+7 (473) 200-10-10", "Пн-Пт 08:00-20:00, Сб 09:00-16:00"),
            ("Клиника Семейная", "г. Воронеж, Московский пр-т, 88", "+7 (473) 210-22-33", "Пн-Сб 08:00-21:00"),
            ("Диагностический центр Плюс", "г. Воронеж, ул. Кольцовская, 12", "+7 (473) 250-40-40", "Ежедневно 08:00-20:00"),
        ]
        self.connection.executemany(
            "INSERT INTO clinics (name, address, phone, work_time) VALUES (?, ?, ?, ?)",
            clinics,
        )

        links = [
            (1, 1), (1, 2), (1, 4), (1, 5),
            (2, 1), (2, 2), (2, 3), (2, 4), (2, 5),
            (3, 6), (3, 7), (3, 4), (3, 5),
        ]
        self.connection.executemany(
            "INSERT INTO clinic_services (clinic_id, service_id) VALUES (?, ?)",
            links,
        )
        self.connection.commit()

    def find_patient(self, full_name: str, birth_date: str, policy_number: str, snils: str) -> Patient | None:
        row = self.connection.execute(
            """
            SELECT * FROM patients
            WHERE lower(full_name) = lower(?)
              AND birth_date = ?
              AND upper(policy_number) = upper(?)
              AND snils = ?
            """,
            (full_name.strip(), birth_date.strip(), policy_number.strip(), snils.strip()),
        ).fetchone()
        return self._patient_from_row(row) if row else None

    def get_patient_by_vk(self, vk_user_id: int) -> Patient | None:
        row = self.connection.execute(
            """
            SELECT p.* FROM patients p
            JOIN user_links ul ON ul.patient_id = p.id
            WHERE ul.vk_user_id = ?
            """,
            (vk_user_id,),
        ).fetchone()
        return self._patient_from_row(row) if row else None

    def link_vk_user(self, vk_user_id: int, patient_id: int):
        self.connection.execute(
            """
            INSERT INTO user_links (vk_user_id, patient_id, linked_at)
            VALUES (?, ?, ?)
            ON CONFLICT(vk_user_id) DO UPDATE SET patient_id = excluded.patient_id, linked_at = excluded.linked_at
            """,
            (vk_user_id, patient_id, datetime.now().isoformat(timespec="seconds")),
        )
        self.connection.commit()

    def unlink_vk_user(self, vk_user_id: int):
        self.connection.execute("DELETE FROM user_links WHERE vk_user_id = ?", (vk_user_id,))
        self.connection.commit()

    def list_services(self, category: str | None = None):
        if category:
            return self.connection.execute("SELECT * FROM services WHERE category = ? ORDER BY name", (category,)).fetchall()
        return self.connection.execute("SELECT * FROM services ORDER BY category, name").fetchall()

    def get_service_by_name(self, name: str):
        return self.connection.execute("SELECT * FROM services WHERE lower(name) = lower(?)", (name.strip(),)).fetchone()

    def get_clinic_by_name(self, name: str):
        return self.connection.execute("SELECT * FROM clinics WHERE lower(name) = lower(?)", (name.strip(),)).fetchone()

    def list_clinics(self, service_id: int | None = None):
        if service_id:
            return self.connection.execute(
                """
                SELECT c.* FROM clinics c
                JOIN clinic_services cs ON cs.clinic_id = c.id
                WHERE cs.service_id = ?
                ORDER BY c.name
                """,
                (service_id,),
            ).fetchall()
        return self.connection.execute("SELECT * FROM clinics ORDER BY name").fetchall()

    def create_request(
        self,
        vk_user_id: int,
        patient_id: int | None,
        request_type: str,
        contact: str,
        preferred_time: str,
        comment: str,
        status: str,
        patient_instruction: str = "",
        service_id: int | None = None,
        clinic_id: int | None = None,
    ) -> int:
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        cur = self.connection.execute(
            """
            INSERT INTO requests (
                vk_user_id, patient_id, service_id, clinic_id, request_type,
                contact, preferred_time, comment, status, patient_instruction, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                vk_user_id,
                patient_id,
                service_id,
                clinic_id,
                request_type,
                contact,
                preferred_time,
                comment,
                status,
                patient_instruction,
                now,
                now,
            ),
        )
        self.connection.commit()
        return int(cur.lastrowid)

    def list_user_requests(self, vk_user_id: int):
        return self.connection.execute(
            """
            SELECT r.*, s.name AS service_name, c.name AS clinic_name
            FROM requests r
            LEFT JOIN services s ON s.id = r.service_id
            LEFT JOIN clinics c ON c.id = r.clinic_id
            WHERE r.vk_user_id = ?
            ORDER BY r.id DESC
            LIMIT 5
            """,
            (vk_user_id,),
        ).fetchall()

    @staticmethod
    def _patient_from_row(row) -> Patient:
        return Patient(
            id=row["id"],
            full_name=row["full_name"],
            birth_date=row["birth_date"],
            policy_number=row["policy_number"],
            snils=row["snils"],
            program=row["program"],
            active_until=row["active_until"],
            is_active=bool(row["is_active"]),
        )
